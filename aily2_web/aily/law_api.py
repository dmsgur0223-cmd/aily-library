"""Law.go.kr OPEN API REST adapter. MCP can be added behind this boundary later.

The official endpoints use an OC credential in a query string. Never expose
full request URLs, HTTP exception bodies or credentials to callers/UI/logs.
Only real network calls return data; this module does not substitute mock data.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET

API_ROOT = "https://www.law.go.kr/DRF/"
MAX_BYTES = 3_000_000

class LawAPIError(RuntimeError):
    pass

class _HTTPSLawRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        dest = urlsplit(newurl)
        if dest.scheme != 'https' or dest.hostname not in {'law.go.kr', 'www.law.go.kr'}:
            raise URLError('Law API redirect blocked')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def _secure_urlopen(request, timeout=12):
    return build_opener(_HTTPSLawRedirect()).open(request, timeout=timeout)

@dataclass(frozen=True)
class LawEntry:
    name: str
    law_id: str
    mst: str
    effective_date: str
    ministry: str
    detail_link: str
    promulgation_date: str = ""  # 공포일자 (개정 일자, if amended)
    revision_type: str = ""  # 제개정구분명 from provider


def _request_xml(endpoint: str, params: dict[str, str], *, opener=None) -> ET.Element:
    if endpoint not in {"lawSearch.do", "lawService.do"}:
        raise ValueError("허용되지 않은 법령 API 경로입니다.")
    if not params.get("OC"):
        raise LawAPIError("국가법령정보 OC 인증값이 설정되지 않았습니다.")
    if opener is None:
        opener = _secure_urlopen
    url = API_ROOT + endpoint + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "AILY/4.7 (law API; institutional internal use)", "Accept": "application/xml"})
    try:
        with opener(request, timeout=12) as response:
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise LawAPIError(f"법령 API HTTP 응답 오류 (상태 {exc.code}). 인증값·접속 정책을 확인하세요.") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise LawAPIError("국가법령정보 서버에 접속하지 못했습니다. 인터넷/프록시/방화벽을 확인하세요.") from None
    if len(data) > MAX_BYTES:
        raise LawAPIError("법령 API 응답이 크기 제한(3MB)을 초과했습니다.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise LawAPIError("허용되지 않는 XML 형식입니다.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise LawAPIError("법령 API가 정상 XML을 반환하지 않았습니다. 인증/오류 응답을 확인하세요.") from None
    if root.tag.lower() in {"error", "errorresponse"}:
        raise LawAPIError("법령 API에서 오류를 반환했습니다. OC 인증값과 승인 범위를 확인하세요.")
    return root


def _field(node: ET.Element, *names: str) -> str:
    for name in names:
        value = node.findtext(name)
        if value and value.strip():
            return value.strip()
    return ""


def _safe_law_link(link: str) -> str:
    if not link:
        return ""
    joined = urljoin("https://www.law.go.kr/", link)
    parsed = urlsplit(joined)
    if parsed.scheme != "https" or parsed.hostname not in {"www.law.go.kr", "law.go.kr"}:
        return ""
    # Defensive: do not embed an OC token in UI links.
    if "oc=" in parsed.query.lower():
        return ""
    return joined


def search_laws(oc: str, query: str, *, limit: int = 20, opener=None) -> list[LawEntry]:
    query = query.strip()
    if not 2 <= len(query) <= 80:
        raise ValueError("법령 검색어는 2~80자로 입력하세요.")
    if not 1 <= limit <= 100:
        raise ValueError("검색 결과 개수는 1~100 사이여야 합니다.")
    root = _request_xml("lawSearch.do", {"OC": oc, "target": "law", "type": "XML",
                                           "query": query, "display": str(limit), "page": "1"}, opener=opener)
    entries = []
    # Official XML list responses use <law> (some integrations use <Law>).
    for node in [n for n in root.iter() if n.tag.lower() == "law"][:limit]:
        name = _field(node, "법령명한글", "법령명", "법령명_한글")
        law_id = _field(node, "법령ID")
        mst = _field(node, "법령일련번호")
        if name and (law_id or mst):
            entries.append(LawEntry(name, law_id, mst,
                                    _field(node, "시행일자"),
                                    _field(node, "소관부처명"),
                                    _safe_law_link(_field(node, "법령상세링크")),
                                    _field(node, "공포일자"),
                                    _field(node, "제개정구분명")))
    return entries


def _text_of(node: ET.Element | None) -> str:
    """Collect inline XML text without inventing structure or omitting inline nodes."""
    return "".join(node.itertext()).strip() if node is not None else ""


def _article_number(item: ET.Element, content: str) -> str:
    """Return a label only if present in the official document."""
    number = _field(item, "조문번호")
    branch = _field(item, "조문가지번호")
    if number.isdigit() and int(number) > 0:
        label = f"제{int(number)}조"
        if branch.isdigit() and int(branch) > 0:
            label += f"의{int(branch)}"
        return label
    import re
    match = re.match(r"\s*(제\d+조(?:의\d+)?)", content)
    return match.group(0) if match else ""


def law_articles(oc: str, law_id: str, *, mst: str = "", opener=None) -> dict:
    """Read full article hierarchy from the official promulgation-basis law XML.

    A law article can contain the provision text directly as well as separate
    <항내용>, <호내용>, <목내용> children. Only content returned by the API is
    included, in document order. Nested inline tags are preserved as text.
    """
    identifier = law_id or mst
    if not identifier.isdigit() or len(identifier) > 16:
        raise ValueError("조회할 법령 식별자가 올바르지 않습니다.")
    id_param = {"ID": identifier} if law_id else {"MST": identifier}
    root = _request_xml("lawService.do", {"OC": oc, "target": "law", "type": "XML", **id_param}, opener=opener)
    header = root.find("기본정보")
    title = _field(root, "법령명_한글", "법령명한글", "법령명")
    effective_date = _field(root, "시행일자")
    if header is not None:
        title = title or _field(header, "법령명_한글", "법령명한글", "법령명")
        effective_date = effective_date or _field(header, "시행일자")

    articles = []
    for item in root.iter("조문단위"):
        parts = []
        # A single 조문내용 often does not contain the subordinate clauses.
        # Preserve the sequence of the official XML rather than reconstruct it.
        for piece in item.iter():
            if piece.tag not in {"조문내용", "항내용", "호내용", "목내용"}:
                continue
            value = _text_of(piece)
            if value and not any(value == existing or value in existing for existing in parts):
                parts.append(value)
        if not parts:
            continue
        content = "\n".join(parts)
        number = _article_number(item, content)
        heading = _field(item, "조문제목")
        label = (number + (f"({heading})" if heading else "")) if number else heading
        articles.append({"title": label, "content": content,
                         "article_number": number,
                         "article_effective_date": _field(item, "조문시행일자")})
    # Source is a promulgation-basis law query (target=law); the displayed
    # enforcement date is a literal metadata field, NOT a legal applicability verdict.
    return {"title": title, "effective_date": effective_date,
            "source_basis": "공포일 기준 법령 본문(target=law)", "articles": articles}


def compare_old_new(oc: str, *, law_id: str = '', mst: str = '', opener=None) -> dict:
    """Read official 신구법 comparison (oldAndNew), without inventing missing changes."""
    if not (mst or law_id) or any(not x.isdigit() or len(x)>16 for x in (law_id,mst) if x):
        raise ValueError('법령 ID/MST 형식이 올바르지 않습니다.')
    # Prefer exact search-result MST to avoid comparing a different revision.
    params = {'MST':mst} if mst else {'ID':law_id}
    root = _request_xml('lawService.do', {'OC': oc,'target':'oldAndNew','type':'XML',**params}, opener=opener)
    exists = _field(root,'신구법존재여부','신구법_존재여부')
    if exists == 'N':
        return {'available':False, 'message':'해당 법령 시점의 신구 조문 비교 자료가 없습니다.', 'changes':[]}
    def metadata(side):
        for container in (root.find(f'.//{side}_기본정보'),root.find(f'.//{side}기본정보')):
            if container is not None:
                return {'promulgation_date':_field(container,'공포일자'),
                        'effective_date':_field(container,'시행일자'),
                        'revision_type':_field(container,'제개정구분명')}
        return {}
    def articles(side):
        out={}
        for node in root.findall(f'.//{side}목록/조문')[:250]:
            txt=_text_of(node)
            if not txt:continue
            idx=_field(node,'조문번호','조문키','조문ID','조문일련번호')
            if not idx:
                import re
                found=re.search(r'제\s*\d+\s*조(?:의\s*\d+)?',txt)
                idx=found.group(0).replace(' ','') if found else f'원문순서_{len(out)+1}'
            out[idx]=txt[:6000]
        return out
    old=articles('구조문'); new=articles('신조문')
    if not old and not new:
        return {'available':False,'message':'API는 응답했지만 비교 가능한 구조문·신조문을 추출하지 못했습니다. 원문을 확인하세요.',
                'changes':[], 'old':metadata('구조문'), 'new':metadata('신조문')}
    changes=[]
    for idx in dict.fromkeys([*old,*new]):
        before=old.get(idx,'');after=new.get(idx,'')
        if before==after:continue
        change_type = '변경' if before and after else '삭제' if before else '신설'
        # Deterministic summary of observed text, not a guess about legal effect.
        if change_type == '변경':
            import difflib
            a,b=before.split(),after.split()
            matcher=difflib.SequenceMatcher(a=a,b=b,autojunk=False)
            removed=[];added=[]
            for op,a1,a2,b1,b2 in matcher.get_opcodes():
                if op in ('replace','delete'):removed.extend(a[a1:a2])
                if op in ('replace','insert'):added.extend(b[b1:b2])
            summary='개정 전 표현: '+(' '.join(removed)[:120] or '동일')+' / 개정 후 표현: '+(' '.join(added)[:120] or '동일')
        else:
            summary='기존 조문 삭제' if change_type == '삭제' else '새 조문 신설'
        changes.append({'article':idx,'type':change_type,'summary':summary,
                        'before':before[:3000],'after':after[:3000]})
    return {'available':True,'changes':changes[:20], 'change_count':len(changes),
            'truncated':len(changes)>20, 'old':metadata('구조문'),'new':metadata('신조문'),
            'source':'국가법령정보 신구법 API (oldAndNew)',
            'note':'API에서 제공된 신구 조문만 비교했습니다. 공포일과 시행일이 다를 수 있으며 적용 여부는 별도 확인해야 합니다.'}

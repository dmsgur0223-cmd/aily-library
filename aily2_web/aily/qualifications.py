"""Q-Net public-data national qualification names for advisory book screening.

Official source: https://www.data.go.kr/data/15003024/openapi.do
This is *national* technical/professional qualification list, not the separate
state-accredited private qualifications dataset. The credential never enters logs,
cache JSON, bibliographic queries or a shared deployment.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

QNET_ENDPOINT = 'https://openapi.q-net.or.kr/api/service/rest/InquiryListNationalQualifcationSVC/getList'
QNET_OFFICIAL_HTTP = 'http://openapi.q-net.or.kr/api/service/rest/InquiryListNationalQualifcationSVC/getList'
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / 'data' / 'qualifications_cache.json'
CACHE_SCHEMA = 1


def local_qnet_http_allowed(root: Path) -> bool:
    """Local-only Q-Net preference: ON when unset, explicit opt-out survives restarts.

    The public web application continues to require a separate opt-in and
    direct API callers still default to HTTPS-only.
    """
    consent_file = root / 'config' / 'qnet_http_consent.txt'
    try:
        saved = consent_file.read_text(encoding='utf-8').strip().lower()
    except FileNotFoundError:
        return True
    except (OSError, UnicodeError):
        return False
    return saved == 'allow'


def normalize_qualification_name(name: str) -> str:
    return re.sub(r'[^0-9A-Za-z가-힣]', '', str(name or '')).casefold()


def names_from_xml(payload: bytes) -> tuple[set[str], int | None]:
    """Strictly parse successful Q-Net XML, rejecting an error disguised as HTTP 200."""
    if len(payload) > 3_000_000:
        raise RuntimeError('자격종목 API 응답이 너무 큽니다.')
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise RuntimeError('자격종목 API가 올바른 XML을 반환하지 않았습니다.') from None
    def tag_name(tag: str) -> str:
        return tag.split('}', 1)[-1].lower()
    for element in root.iter():
        if tag_name(element.tag) in ('resultcode','returnreasoncode') and (element.text or '').strip() not in ('00','0','000','200'):
            # Do not show raw response or query URL containing a credential.
            raise RuntimeError('자격종목 API가 요청을 거부했습니다. 인증키 활성화·활용승인·호출 제한을 확인하세요.')
    names = {
        (element.text or '').strip()
        for element in root.iter()
        if tag_name(element.tag) == 'jmfldnm' and (element.text or '').strip()
    }
    total = None
    for element in root.iter():
        if tag_name(element.tag) == 'totalcount' and (element.text or '').strip().isdigit():
            total = int((element.text or '').strip())
            break
    return names, total


def fetch_qnet_qualifications(key: str, opener=None, allow_insecure_http: bool = False) -> tuple[set[str], dict]:
    """Refresh from official Q-Net endpoint; no credential persists in the result.

    HTTPS is preferred. The local app can explicitly configure a plaintext HTTP
    fallback; other callers remain HTTPS-only unless opted in by their operator.
    HTTP is only attempted after a HTTPS transport/connection failure, not when
    the HTTPS endpoint rejects a key or returns unusable data.
    """
    if not str(key or '').strip():
        raise ValueError('공공데이터포털 국가자격 종목정보 API 키가 없습니다.')
    if opener is None:
        opener = urlopen
    endpoints = [QNET_ENDPOINT] + ([QNET_OFFICIAL_HTTP] if allow_insecure_http else [])
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            found = set()
            count = None
            previous_page = None
            # API only requires serviceKey; pagination support varies by provider.
            for page in range(1, 201):
                params = {'serviceKey': str(key).strip(), 'pageNo': page, 'numOfRows': 3000}
                request = Request(endpoint + '?' + urlencode(params), headers={'User-Agent':'AILY/4.6 qualification-list'})
                with opener(request, timeout=18) as response:
                    data = response.read(3_000_001)
                page_names, total = names_from_xml(data)
                if not page_names:
                    if page == 1:
                        raise RuntimeError('자격종목 API 응답에 종목명이 없습니다. 승인 상태나 응답 형식을 확인하세요.')
                    break
                if page_names == previous_page:
                    break
                previous_page = page_names
                found.update(page_names)
                count = total if total is not None else count
                if count is None or len(found) >= count:
                    break
            if not found or (count is not None and len(found) < count) or (count is None and len(found) < 50):
                raise RuntimeError('자격종목 API 목록을 완전히 가져오지 못했습니다. 다시 갱신해 주세요.')
            return found, {'source':'Q-Net 국가자격 종목 목록 API','updated_at':datetime.now(timezone.utc).isoformat(),
                           'count':len(found),'transport':'HTTPS' if endpoint.startswith('https:') else 'HTTP (암호화되지 않음)',
                           'scope':'국가기술자격·국가전문자격 (국가공인 민간자격은 별도)'}
        except HTTPError:
            # A server-side rejection is not a TLS/connectivity failure.
            # Never resend an API key over cleartext HTTP for this case.
            raise RuntimeError('Q-Net 서버가 요청을 거부했습니다. 인증키·활용승인·서버 상태를 확인하세요.') from None
        except RuntimeError:
            # Invalid XML, rejected API status, incomplete list: no insecure retry.
            raise
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            # Only real network/TLS failures may trigger the optional HTTP fallback.
            continue
    raise RuntimeError('Q-Net 자격종목 API 연결 실패. 인터넷·기관 방화벽 또는 HTTP 허용 옵션을 확인하세요.') from None


def read_qualification_cache(path: Path = DEFAULT_CACHE) -> tuple[set[str], dict]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') != CACHE_SCHEMA or not isinstance(data.get('names'), list):
            return set(), {}
        names = {str(n).strip() for n in data['names'] if isinstance(n, str) and n.strip()}
        return names, {k:data.get(k) for k in ('source','updated_at','count','transport','scope')}
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return set(), {}


def refresh_qualification_cache(key: str, path: Path = DEFAULT_CACHE, *, opener=None,
                                allow_insecure_http: bool = False) -> tuple[set[str], dict]:
    names, metadata = fetch_qnet_qualifications(key, opener, allow_insecure_http)
    payload = {'schema': CACHE_SCHEMA, 'names': sorted(names), **metadata}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return names, metadata


# A small set of words that unambiguously describe examination/study materials.
# A qualification *name by itself* must never be a reason for exclusion.
EXAM_MATERIAL = re.compile(
    r'기출(?:예상)?문제|(?:예상|적중|실전|모의|단원|출제)문제|문제집|문제은행|'
    r'실전모의고사|모의고사|필기(?:시험|대비|완성|합격|기본서|핵심|기출|실전)?|'
    r'실기(?:시험|대비|완성|합격|기본서|핵심|기출|실전)?|'
    r'(?:시험|자격증|필기|실기|수험)\s*(?:대비|준비|공부|교재|기본서|합격)|'
    r'(?:단기|초단기|최종|한권으로|단번에|빠른)\s*합격|합격(?:비법|전략|가이드|보장|수기집|수험서|교재|노트)|'
    r'수험서|기본서|교재|수험\s*(?:핵심|요약|공부)|'
    r'핵심이론|핵심요약|합격노트|시험총정리|시험공략', re.I)

# Clear title-level five-type clues. General education books like '수학이 필요한 순간'
# and '공인중개사가 알려주는 부동산 상식' don't match these patterns.
DIRECT_EXCLUSIONS = [
    ('문제집', re.compile(r'문제집|기출문제|예상문제|단원평가|평가문제|문제은행|모의고사|실전문제|적중문제', re.I)),
    ('참고서', re.compile(r'참고서|자습서|내신대비|교과서\s*(?:자습서|평가문제)|수능특강|수능완성', re.I)),
    ('수험서', re.compile(r'수험서|수험\s*(?:대비|교재|기본서)|공무원\s*(?:시험|기출|필기|실기)\s*(?:대비|교재|문제|합격)|'
                             r'채용시험\s*(?:대비|교재|문제|합격)|수능\s*(?:대비|기출|모의고사)|'
                             r'\bNCS\s*(?:시험|기출|실전|직업기초|문제집)', re.I)),
    ('전문·전공서', re.compile(r'전문[·\s-]*전공서|전문서적|전공서적|전공\s*자료|전문\s*교재|전공\s*도서', re.I)),
    ('대학교재', re.compile(r'대학교재|대학\s*(?:전공\s*)?교재|대학교\s*(?:전공\s*)?교재|'
                              r'전공\s*(?:교재|교과서|수험서)|대학\s*강의용\s*교재|대학\s*전공서적', re.I)),
]


CACHE_TTL_DAYS = 30


def ensure_qualification_cache(key: str, path: Path = DEFAULT_CACHE, *,
                               max_age_days: int = CACHE_TTL_DAYS, now=None,
                               refresher=None, allow_insecure_http: bool = False) -> tuple[set[str], dict]:
    """Use a recent local list, otherwise fetch automatically once on demand.

    Does not send a service key via HTTP without explicit opt-in. Errors do not
    convert unverified books to screening passes. Authentication is only needed
    when refreshing, and credentials are never written into the cache.
    """
    names, meta = read_qualification_cache(path)
    current = now or datetime.now(timezone.utc)
    timestamp = meta.get('updated_at')
    try:
        updated = datetime.fromisoformat(str(timestamp).replace('Z','+00:00'))
        if updated.tzinfo is None: raise ValueError('timezone missing')
        fresh = 0 <= (current - updated).total_seconds() < max_age_days * 86400
    except (TypeError, ValueError, OverflowError):
        fresh = False
    if names and fresh:
        return names, {**meta, 'cache_status':'재사용'}
    if not str(key or '').strip():
        raise RuntimeError('Q-Net API 인증값이 저장되지 않았습니다. config/qnet_api_key.txt 설정이 필요합니다.')
    refresh = refresher or refresh_qualification_cache
    result, detail = refresh(key, path, allow_insecure_http=allow_insecure_http)
    return result, {**detail, 'cache_status':'자동 갱신'}


# The first seven categories are enabled by default; comics are opt-in.
SECOND_FILTER_CATEGORIES = (
    '수험서·자격증 교재',
    '문제집·기출문제집',
    '교과서·학습참고서·전공교재',
    '사전·연감·백서·보고서',
    '악보집·대본집·전시도록',
    '퍼즐북·스티커북·컬러링북',
    '워크북·쓰기익힘책·필사책',
    '만화·웹툰·그래픽노블',
)
DEFAULT_SECOND_CATEGORIES = SECOND_FILTER_CATEGORIES[:7]
# Existing external callers can still pass the 4.8.1 category names.
LEGACY_SECOND_CATEGORIES = ('문제집','참고서','수험서','자격증 교재','대학교재','전문·전공서')
STUDY_CATEGORIES = frozenset(SECOND_FILTER_CATEGORIES + LEGACY_SECOND_CATEGORIES)

# Restrict automatic exclusions to explicit book-type wording. These rules are
# heuristic text classifiers, not proof that a book belongs to the category.
NEW_EXCLUSIONS = (
    ('문제집·기출문제집', re.compile(r'문제집|기출(?:예상)?문제(?:집)?|예상문제집|평가문제집|실전문제집|문제은행|모의고사|단원평가문제', re.I)),
    ('수험서·자격증 교재', re.compile(r'수험서|자격증\s*(?:대비|교재|문제집|기본서)|공무원\s*(?:시험|기출|필기|실기)|시험\s*(?:대비|교재|기출)|\bNCS\s*(?:기출|시험|문제)|합격(?:기본서|문제집|교재)', re.I)),
    ('교과서·학습참고서·전공교재', re.compile(r'교과서|학습참고서|참고서|자습서|내신대비|수능특강|수능완성|대학교재|대학\s*(?:전공\s*)?교재|대학\s*강의용\s*교재|전공\s*(?:교재|서적|도서)|전문\s*(?:교재|전공서)', re.I)),
    ('사전·연감·백서·보고서', re.compile(r'백과사전|국어사전|영어사전|용어사전|연감|백서|연차보고서|정책보고서|연구보고서|사업보고서|통계보고서|\bDictionary\b', re.I)),
    ('악보집·대본집·전시도록', re.compile(r'악보집|악보\s*모음집|연주곡집|대본집|시나리오집|극본집|전시\s*도록|전시도록|전시회\s*도록', re.I)),
    ('퍼즐북·스티커북·컬러링북', re.compile(r'퍼즐북|스티커북|컬러링북|컬러링\s*북|색칠공부책|색칠북|미로찾기북', re.I)),
    ('워크북·쓰기익힘책·필사책', re.compile(r'워크북|쓰기익힘책|따라쓰기\s*(?:책|교재|워크북)|필사책|필사노트|필사\s*워크북', re.I)),
    ('만화·웹툰·그래픽노블', re.compile(r'웹툰|그래픽\s*노블|학습만화|만화책|만화판|코믹스', re.I)),
)


def classify_study_material(record: dict, qualifications: set[str] | None,
                            enabled_categories=None) -> dict:
    """Evidence-bound second filter. A pass is not a purchasing decision."""
    enabled = frozenset(DEFAULT_SECOND_CATEGORIES if enabled_categories is None else enabled_categories)
    if not enabled.issubset(STUDY_CATEGORIES):
        raise ValueError('지원하지 않는 2차 검사 항목입니다.')
    if not enabled:
        return {'status':'검사 안 함','category':'설정 미사용','evidence':'2차 유형 검사 비활성화'}
    if not record:
        return {'status':'조회 실패','category':'서지 미확인',
                'evidence':'YES24 ISBN 일치 상품정보가 없어 2차 검사를 수행하지 못했습니다.'}
    title = str(record.get('TITLE') or '').strip()
    subtitle = str(record.get('SUBTITLE') or '').strip()
    display_title = title + (' ' + subtitle if subtitle else '')
    provider = str(record.get('SOURCE') or '도서정보')
    detail = str(record.get('FORM_DETAIL') or '').strip()
    # Broad KDC subject tags are NOT exclusion evidence by themselves.
    if not title:
        return {'status':'조회 실패','category':'서명 누락','evidence':'ISBN 일치 서지정보에 서명이 없어 검사하지 못했습니다.'}
    patterns = list(NEW_EXCLUSIONS)
    patterns.extend(DIRECT_EXCLUSIONS)   # legacy compatibility
    for category, pattern in patterns:
        if category not in enabled:
            continue
        found = pattern.search(display_title) or pattern.search(detail)
        if found:
            source = '서명·부제' if pattern.search(display_title) else '자료형태'
            return {'status':'2차 탈락','category':category,
                    'evidence':f'{provider} {source}의 「{found.group(0)}」로 {category} 제외 기준에 해당함 (최종 처리 담당자 결정)'}
    qnet_enabled = bool(enabled & {'수험서·자격증 교재','자격증 교재'})
    if qnet_enabled:
        if not qualifications:
            return {'status':'조회 실패','category':'Q-Net 조회 실패',
                    'evidence':'Q-Net 국가자격 종목 목록을 불러오지 못해 자격증 교재 검사를 완료하지 못했습니다.'}
        normalized_title = normalize_qualification_name(title)
        matches = sorted(
            (name for name in qualifications if len(normalize_qualification_name(name)) >= 3
             and normalize_qualification_name(name) in normalized_title),
            key=lambda name:len(normalize_qualification_name(name)), reverse=True)
        if matches:
            exam_clue = EXAM_MATERIAL.search(title)
            if exam_clue:
                return {'status':'2차 탈락','category':'자격증 교재',
                        'evidence':f'Q-Net 자격종목 「{matches[0]}」 및 서명의 시험교재 표현 「{exam_clue.group(0)}」가 확인됨 (최종 처리 담당자 결정)'}
            return {'status':'2차 통과','category':'제외 근거 없음',
                    'evidence':f'Q-Net 자격종목 「{matches[0]}」이 등장하지만 시험·교재임을 확인할 수 있는 근거가 없음 (최종 선정 아님)'}
    return {'status':'2차 통과','category':'제외 근거 없음',
            'evidence':f'{provider} 서지정보에서 활성화된 제외 유형에 해당하는 명확한 근거가 확인되지 않음 (최종 선정 아님)'}

"""Conservative natural-language routing to the existing, read-only Law MCP Hub.

Only explicit, recognizable *law titles* become lookup candidates. Results are
search leads and literal API excerpts, NEVER findings of legality or applicability.
No uploaded/institutional documents are read or indexed here.
"""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import quote

from .mcp_client import MCPConnectionError, law_articles_mcp, search_laws_mcp

# These are title-query *candidates*, not assumptions about which law applies.
EXPLICIT_TITLES = (
    ('지방자치단체를당사자로하는계약에관한법률', '지방자치단체를 당사자로 하는 계약에 관한 법률'),
    ('지방자치단체출자출연기관의운영에관한법률', '지방자치단체 출자·출연 기관의 운영에 관한 법률'),
    ('공공기관의운영에관한법률', '공공기관의 운영에 관한 법률'),
    ('개인정보보호법', '개인정보 보호법'),
    ('지방공기업법', '지방공기업법'),
    ('지방자치법', '지방자치법'),
    ('독서문화진흥법', '독서문화진흥법'),
    ('도서관법', '도서관법'),
)

# Narrow domain hints. Never infer a foundation's juridical character.
DOMAIN_HINTS = (
    ('개인정보', '개인정보 보호법'),
    ('도서관', '도서관법'),
    ('독서문화', '독서문화진흥법'),
    ('지방공기업', '지방공기업법'),
    ('지방계약', '지방자치단체를 당사자로 하는 계약에 관한 법률'),
    ('출자출연기관', '지방자치단체 출자·출연 기관의 운영에 관한 법률'),
)

TOPIC_HINTS = (
    '독서문화', '개인정보', '도서관서비스', '자료의수집', '대출',
    '위탁', '수집', '시설', '계약', '강사', '프로그램', '행사',
)

LEGAL_CUES = (
    '법적근거', '법령', '법률', '조문', '위법', '적법', '합법', '상위법',
    '시행령', '시행규칙', '법적으로', '근거법', '법적문제', '법에따라',
    '법에근거', '법적인', '법률상', '법규',
)


def _compact(text: str) -> str:
    return re.sub(r'[\s·･․ㆍ\-]+', '', text or '').casefold()


def wants_law_research(question: str) -> bool:
    """Trigger for legal questions; do not enable indiscriminate API requests."""
    query = _compact(question)
    return (any(cue in query for cue in LEGAL_CUES)
            or any(title in query for title, _ in EXPLICIT_TITLES)
            or ('근거' in query and any(word in query for word in
                                      ('사업', '행사', '프로그램', '계약', '도서관', '추진'))))


def propose_law_titles(question: str, override: str = '') -> tuple[str, ...]:
    """No freeform generation: explicit title beats domain hints; max three leads."""
    if override.strip():
        title = override.strip()
        if not 2 <= len(title) <= 80 or any(ord(c) < 32 for c in title):
            raise ValueError('법령명은 2~80자 일반 문자로 입력하세요.')
        return (title,)
    compact = _compact(question)
    named = []
    for phrase, title in EXPLICIT_TITLES:
        if phrase in compact and title not in named:
            named.append(title)
    if named:
        return tuple(named[:3])
    for cue, title in DOMAIN_HINTS:
        if cue in compact and title not in named:
            named.append(title)
    return tuple(named[:3])


def topic_keyword(question: str) -> str:
    compact = _compact(question)
    for topic in TOPIC_HINTS:
        if _compact(topic) in compact:
            return topic
    return ''


# Each expansion is only a *literal search expression*. No synonym establishes
# that a statute applies to the user's organization or proposed activity.
RELATED_EXPRESSIONS = {
    '독서문화': ('독서 문화', '독서활동', '독서생활', '독서', '문화활동', '독서진흥', '문화프로그램'),
    '도서관서비스': ('도서관 서비스', '도서관의 업무', '서비스', '정보제공'),
    '자료의수집': ('자료 수집', '도서관자료', '자료의 수집'),
    '프로그램': ('문화프로그램', '문화 프로그램', '교육프로그램', '문화활동', '평생학습'),
    '행사': ('문화행사', '독서행사', '문화활동'),
    '강사': ('강사', '강사료', '강사수당'),
    '대출': ('자료대출', '도서관자료의 대출'),
}


def related_expressions(topic: str) -> list[str]:
    return list(RELATED_EXPRESSIONS.get(topic, ()))[:8]


def run_law_research(root: Path, question: str, *, law_name: str = '') -> dict:
    """MCP calls only. Returns verifiable search/article excerpts, not an AI verdict.

    Fail closed: an upstream exception is recorded as a safe *error*, not
    mistaken for no matching provision or an affirmative legal finding.
    """
    if not 2 <= len(question.strip()) <= 1800:
        raise ValueError('업무 질문은 2~1800자로 입력하세요.')
    titles = propose_law_titles(question, law_name)
    outcome = {
        'question': question.strip(), 'method': '읽기 전용 MCP 자동 검색 (규칙 기반 후보 선택)',
        'titles': titles, 'laws': [], 'errors': [], 'keyword': topic_keyword(question),
        'attempted': False, 'related_terms': related_expressions(topic_keyword(question)),
        'caution': ('검색 후보는 업무 관련 법령의 적용 여부를 의미하지 않습니다. '
                    '시행일·적용 대상·특별법/조례/내규 및 법령 원문은 담당자가 확인해야 합니다.'),
    }
    if not titles:
        return outcome
    for title in titles:
        outcome['attempted'] = True
        item = {'query': title, 'name': '', 'effective_date': '', 'ministry': '',
                'url': '', 'identifier': '', 'articles': [], 'matched_article_count': 0,
                'truncated': False, 'status': '검색 중',
                'detail_effective_date': '', 'source_basis': '', 'article_total': None}
        outcome['laws'].append(item)
        try:
            matches = search_laws_mcp(root, title, limit=25)
        except (MCPConnectionError, ValueError):
            item['status'] = 'API 조회 실패'
            outcome['errors'].append(f'{title}: MCP 검색 또는 국가법령정보 API 조회 실패')
            continue
        # A different title containing the query is not proof that the exact
        # intended statute was located. Never grab the first partial match.
        exact = next((law for law in matches if _compact(law.name) == _compact(title)), None)
        if exact is None:
            item['status'] = '법령명 정확 일치 결과 없음'
            continue
        item.update(name=exact.name, identifier=(exact.law_id or exact.mst), effective_date=exact.effective_date,
                    ministry=exact.ministry, url=(exact.detail_link or
                    'https://www.law.go.kr/법령/' + quote(exact.name, safe='')),
                    status='법령명 조회됨 · 관련 조문 미확인')
        if not (exact.law_id or exact.mst):
            continue
        # A keyword is required to show *topic-matched* provisions. No keyword
        # means no articles are selected by guesswork.
        if not outcome['keyword']:
            item['status'] = '법령명 조회됨 · 조문 키워드 미식별'
            continue
        try:
            detail = law_articles_mcp(root, exact.law_id, mst=exact.mst,
                                      keyword=outcome['keyword'], limit=6,
                                      related_terms=outcome['related_terms'])
        except (MCPConnectionError, ValueError):
            item['status'] = '조문 API 조회 실패'
            outcome['errors'].append(f'{title}: MCP 조문 조회 실패')
            continue
        # A valid tool call does not prove that the returned *law identity*
        # matches the search result. Never show excerpts from another statute.
        detail_title = detail.get('title')
        if isinstance(detail_title, str) and detail_title.strip() and _compact(detail_title) != _compact(exact.name):
            item['status'] = '검색 목록과 법령 본문 명칭 불일치'
            outcome['errors'].append(f'{title}: 법령 본문 명칭이 검색 결과와 달라 원문 확인 필요')
            continue
        found = detail.get('articles')
        if not isinstance(found, list):
            item['status'] = '조문 응답 형식 오류'
            outcome['errors'].append(f'{title}: 조문 응답 형식 오류')
            continue
        verified = []
        for article in found:
            if not isinstance(article, dict):
                continue
            text = article.get('content')
            heading = article.get('title')
            if isinstance(text, str) and text.strip() and isinstance(heading, str):
                verified.append({'title': heading[:180], 'content': text[:6000],
                                 'article_number': str(article.get('article_number', ''))[:40],
                                 'article_effective_date': str(article.get('article_effective_date', ''))[:20],
                                 'matched_term': str(article.get('matched_term', ''))[:80],
                                 'match_kind': str(article.get('match_kind', ''))[:80]})
        item['articles'] = verified
        item['detail_effective_date'] = str(detail.get('effective_date') or '')[:20]
        item['source_basis'] = str(detail.get('source_basis') or '')[:90]
        item['article_total'] = detail.get('article_total') if isinstance(detail.get('article_total'), int) else None
        if item['article_total'] == 0:
            item['status'] = '법령 조회됨 · API에서 조문을 추출하지 못함'
            outcome['errors'].append(f'{title}: 법령 본문에서 조문 추출 실패 · 법령 원문 확인 필요')
            continue
        item['matched_article_count'] = detail.get('matched_article_count', 0)
        item['truncated'] = bool(detail.get('truncated', False))
        item['status'] = (('조문 문구 일치 후보 조회됨 · 법적 적용성 미검증' if verified else
                           '키워드 일치 조문 없음 · 법적 근거 미확인'))
    return outcome

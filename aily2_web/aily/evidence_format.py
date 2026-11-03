"""Evidence cards from remote public datasets. Unknown fields remain unknown.

This is field mapping, not a factual/legal assessment. No source metadata is invented.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit

TITLE_KEYS = ('title','name','statNm','stat_name','bidNtceNm','bid_notice_name','사업명','공고명','법령명','제목','도서명','통계표명')
DATE_KEYS = ('date','baseDate','data_date','updatedAt','createdAt','기준일','작성일','공고일','시행일','년도','연도')
SOURCE_KEYS = ('publisher','provider','agency','institution','source','발행기관','제공기관','기관명')
URL_KEYS = ('url','link','detailUrl','sourceUrl','원문','링크','상세URL')
ROW_KEYS = ('items','rows','results','result','list','data','documents','통계표','목록')


def _pick(value: dict, keys) -> str:
    for key in keys:
        item = value.get(key)
        if isinstance(item, (str,int,float)) and str(item).strip(): return str(item).strip()[:300]
    return ''


def _safe_source_url(url: str) -> str:
    if not url or len(url)>1500: return ''
    try:
        parts=urlsplit(url)
        if parts.scheme=='https' and parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment:
            return url
    except ValueError: pass
    return ''


def extract_evidence(data, provider_host: str, *, max_rows=8) -> list[dict]:
    """Returns only source fields actually present in tool outputs."""
    work=[data]
    records=[]
    while work and len(records)<max_rows:
        item=work.pop(0)
        if isinstance(item,list):
            work[:0]=item[:max_rows]
        elif isinstance(item,dict):
            if any(k in item for k in TITLE_KEYS):
                records.append({'title':_pick(item,TITLE_KEYS) or '제목 미제공',
                                'reference_date':_pick(item,DATE_KEYS) or '미제공',
                                'source':_pick(item,SOURCE_KEYS) or provider_host,
                                'url':_safe_source_url(_pick(item,URL_KEYS)),
                                'verified':False})
            else:
                for key in ROW_KEYS:
                    if isinstance(item.get(key), (dict,list)):
                        work.append(item[key])
        # Scalar result doesn't have a verifiable title/date/source.
    return records


def score_tool(question: str, meta: dict) -> int:
    """Ranking assistance only. No claim of semantic understanding/authority."""
    name=str(meta.get('name','')).casefold()
    desc=str(meta.get('description','')).casefold()[:250]
    if not name or not re.search(r'search|find|query|lookup|list|조회|검색|찾기',name+' '+desc):
        return 0
    words=[w.casefold() for w in re.findall(r'[가-힣a-zA-Z0-9]{2,}',question)]
    stop={'알려줘','찾아줘','어떤','대한','관련','있어','있나','조회','검색','뭐야','어떻게'}
    useful=[w for w in words if w not in stop]
    score=1
    for word in useful:
        if word in name: score+=5
        elif word in desc: score+=2
    return score

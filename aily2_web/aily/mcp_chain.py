"""Bounded, evidence-based multi-tool MCP queries (KOSIS initial adapter).

No guesses for table/region/classification IDs. Outputs are leads until an actual
get_data response returns records; never turn a table search into a statistic.
"""
from __future__ import annotations
import re
from typing import Callable
from .remote_mcp import safe_auto_tool_name, public_search_question

_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')

def _text(value):
    if isinstance(value, str): return value[:13000]
    if isinstance(value, dict): return '\n'.join(_text(v) for v in value.values())[:13000]
    if isinstance(value, list): return '\n'.join(_text(v) for v in value[:15])[:13000]
    return ''

def _candidates(data):
    """Extract only identifiers explicitly emitted by the upstream tool."""
    text = _text(data)
    pairs = []
    for m in re.finditer(r'(?:통계표ID|통계표 ID|tblId|TBL_ID|tbl_id)\*{0,2}\s*[：:=]\s*[`\s]*([A-Za-z0-9_-]+)', text, re.I):
        tail=text[max(0,m.start()-250):m.end()+120]
        org=re.search(r'(?:기관ID|기관코드|orgId|ORG_ID)\*{0,2}\s*[：:=]\s*[`\s]*([A-Za-z0-9_-]+)',tail,re.I)
        table=m.group(1)
        if _ID.fullmatch(table) and org and _ID.fullmatch(org.group(1)):
            pairs.append((org.group(1),table))
    def walk(x):
        if isinstance(x,dict):
            org=next((x.get(k) for k in ('orgId','ORG_ID','org_id','기관ID') if x.get(k)),None)
            tbl=next((x.get(k) for k in ('tblId','TBL_ID','tbl_id','통계표ID') if x.get(k)),None)
            if isinstance(org,(str,int)) and isinstance(tbl,str) and _ID.fullmatch(str(org)) and _ID.fullmatch(tbl): pairs.append((str(org),tbl))
            for y in list(x.values())[:25]: walk(y)
        elif isinstance(x,list):
            for y in x[:15]: walk(y)
    walk(data)
    return list(dict.fromkeys(pairs))[:4]

def _region(question):
    match=re.search(r'(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도|인천|서울|부산|대구|광주|대전|울산|세종)', question)
    return match.group(0) if match else ''

def _data_presence(data):
    """A successful tool message is not necessarily a numeric observation."""
    if isinstance(data,dict):
        for k in ('rows','items','results','data','result'):
            if isinstance(data.get(k),list) and data[k]: return True
            if isinstance(data.get(k),dict) and _data_presence(data[k]): return True
    if isinstance(data,list): return bool(data)
    text=_text(data)
    return bool(re.search(r'(?:수치|통계값|DATA_VALUE|DT|데이터)\s*[：:=]\s*[-+]?\d[\d,]*(?:\.\d+)?',text,re.I))

def _rejected(data):
    """Only consider the actual validation verdict, not provider help examples.

    KOSIS often appends a generic '판단' section listing both success and
    failure actions. Matching '❌ 부적합' anywhere erroneously rejects *every*
    validated table, including verified matches.
    """
    if isinstance(data,dict) and data.get('suitable') is False:
        return True
    s=_text(data)
    actual=re.split(r'(?m)^\s*#{1,4}\s*판단\b',s, maxsplit=1)[0]
    return bool(re.search(r'(?m)^\s*#{2,4}\s*(?:🚫\s*)?(?:교차분류 부적합|요청 구간 미수록|❌\s*부적합)\b',actual)
        or re.search(r'(?m)^\s*[-*]\s*(?:결론|판정|검증결과)\s*[:：]\s*(?:부적합|실패)',actual))

def chain_kosis(question: str, tools: list[dict], call: Callable[[str,dict],dict], *, max_calls=6) -> dict:
    """Search -> validate -> region code -> data, using observed upstream identifiers.

    Any missing required axis/item selection stops rather than defaulting to ALL.
    All tool calls are read-only with bounded count and allowlisted names.
    """
    names={t['name']:t.get('input_schema',{}) for t in tools if safe_auto_tool_name(t.get('name','')) or t.get('name') in ('kosis_validate','kosis_region_code','kosis_table_info','kosis_get_data')}
    steps=[]
    def invoke(name,args):
        if name not in names or len(steps)>=max_calls: return None
        schema=names[name]
        required=schema.get('required',[])
        if not isinstance(required,list) or any(k not in args for k in required): return None
        if any(k not in schema.get('properties',{}) for k in args): return None
        result=call(name,args)
        steps.append({'tool':name,'arguments':{k:v for k,v in args.items() if k not in ('keyword','query')},'ok':bool(result.get('ok')),'result':result})
        return result.get('data') if result.get('ok') else None
    query=public_search_question(question)
    if not query: return {'steps':steps,'status':'blocked','reason':'외부 전송할 수 없는 질문'}
    # Discover a table using tools with a documented search keyword field.
    source=None
    for name in ('kosis_local_search','kosis_search','kosis_item_search'):
        schema=names.get(name,{})
        if not schema: continue
        prop=schema.get('properties',{})
        field='keyword' if 'keyword' in prop else 'query' if 'query' in prop else None
        if not field: continue
        source=invoke(name,{field:query})
        if _candidates(source): break
    choices=_candidates(source)
    if not choices:
        return {'steps':steps,'status':'not_found','reason':'통계표 ID와 기관 ID를 검색 결과에서 확인하지 못했습니다.'}
    org,tbl=choices[0]
    if 'kosis_validate' in names:
        validated=invoke('kosis_validate',{'keyword':query,'orgId':org,'tblId':tbl})
        if validated is None or _rejected(validated):
            return {'steps':steps,'status':'not_verified','reason':'통계표 적합성 검증이 실패하거나 요청된 분류에 맞지 않습니다.'}
    else:
        return {'steps':steps,'status':'not_verified','reason':'통계표 적합성 검증 도구가 없습니다.'}
    # Region code must come from provider, not hand-created from place names.
    area=_region(question)
    code=None
    if area and 'kosis_region_code' in names:
        region_data=invoke('kosis_region_code',{'region':area,'orgId':org,'tblId':tbl})
        if isinstance(region_data,dict):
            for key in ('regionCode','region_code','code','objL1'):
                val=region_data.get(key)
                if isinstance(val,str) and _ID.fullmatch(val): code=val;break
        if not code:
            match=re.search(r'(?:지역코드|regionCode|objL1|코드)\s*[：:=]\s*[`\s]*([A-Za-z0-9_-]+)',_text(region_data),re.I)
            if match: code=match.group(1)
        if not code:
            return {'steps':steps,'status':'needs_selection','reason':'질문 지역에 대응하는 검증된 분류코드를 얻지 못했습니다.'}
    elif area:
        return {'steps':steps,'status':'needs_selection','reason':'지역 분류코드 조회 도구가 없습니다.'}
    args={'orgId':org,'tblId':tbl}
    if code: args['objL1']=code
    # A value-only lookup with no age filter would invent the requested cohort.
    if re.search(r'\d+\s*세\s*이상|\d+\s*대|연령별|남녀별|여성|남성',question) and 'kosis_table_info' not in names:
        return {'steps':steps,'status':'needs_selection','reason':'연령·성별 분류를 확인할 통계표 상세정보 도구가 없습니다.'}
    if re.search(r'\d+\s*세\s*이상|\d+\s*대|연령별|남녀별|여성|남성',question):
        detail=invoke('kosis_table_info',{'orgId':org,'tblId':tbl,'type':'ITM'})
        # Only an exact requested cohort label-to-ID mapping is acceptable.
        requested=re.search(r'(\d+\s*세\s*이상)',question)
        wanted=re.sub(r'\s+','',requested.group(1)) if requested else ''
        if wanted:
            matching=[]
            for line in _text(detail).splitlines():
                norm=re.sub(r'\s+','',line)
                if wanted in norm:
                    code_match=re.search(r'\(([A-Za-z0-9_-]{1,50})\)\s*$',line)
                    if code_match: matching.append(code_match.group(1))
            if len(set(matching))==1: args['itmId']=matching[0]
            else:
                return {'steps':steps,'status':'needs_selection','reason':'요청 연령에 대응하는 통계 항목코드를 유일하게 확인하지 못했습니다.','table':{'orgId':org,'tblId':tbl}}
        else:
            return {'steps':steps,'status':'needs_selection','reason':'요청한 연령·성별 분류의 정확한 코드가 필요합니다.','table':{'orgId':org,'tblId':tbl}}
    if 'kosis_get_data' not in names:
        return {'steps':steps,'status':'needs_selection','reason':'통계 수치 조회 도구가 없습니다.'}
    data=invoke('kosis_get_data',args)
    if not _data_presence(data):
        return {'steps':steps,'status':'no_data','reason':'실제 수치 데이터가 확인되지 않았습니다.'}
    return {'steps':steps,'status':'data_returned','reason':'실제 수치 도구 응답이 반환되었습니다. 단위·기준시점은 별도 확인하세요.','table':{'orgId':org,'tblId':tbl}}

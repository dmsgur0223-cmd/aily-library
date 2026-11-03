"""Shared public-data query router for corporation/external institution screens.

Rule-based question routing; source extracts only. No unsourced answer generation.
Uploads and institution records NEVER leave this module or go to remote MCP.
"""
from __future__ import annotations
from pathlib import Path
import re
from .remote_mcp import (effective_connections, discover, invoke, read_bearer,
                         _query_arguments, BLOCKED_TOOL_NAME, safe_auto_tool_name,
                         public_search_question, invoke_arguments)
from .mcp_presets import is_trusted_builtin
from .mcp_chain import chain_kosis
from .law_assistant import run_law_research, wants_law_research
from .evidence_format import score_tool, extract_evidence

CATEGORY_CUES = {
 'statistics': ('통계','인구','고령','청년','노인','연령','비율','증감','지역현황','이용자수','고령화'),
 'procurement': ('나라장터','발주','조달','입찰','낙찰','계약','물품구입','구매','용역','견적'),
 'business': ('사업자등록','휴업','폐업','사업자번호','업체상태'),
 'library': ('도서관 소장','소장','대출','장서','인기도서','isbn','책','도서'),
 'policy': ('지원사업','공모','사업사례','기관사례','행사사례','정책사업','벤치마킹'),
 'qualification': ('자격증','국가기술자격','국가자격','자격시험','시험일정','NCS','직업능력','일학습병행','훈련과정','합격률','자격종목'),
 'law': ('법령','법적','법률','조례','규정','근거','위법','적법','조문'),
}


def plan_query(question: str) -> list[str]:
    if not 2 <= len(question.strip()) <= 500: raise ValueError('업무 질문은 2~500자로 입력하세요.')
    compact = re.sub(r'\s+', '', question).casefold()
    return [cat for cat, cues in CATEGORY_CUES.items() if any(re.sub(r'\s+', '', cue).casefold() in compact for cue in cues)]


def run_public_research(root: Path, question: str, scope: str, *, external_consent: bool = False,
                        law_title: str = '') -> dict:
    if scope not in ('corp', 'external'): raise ValueError('업무공간 분류 오류')
    categories = plan_query(question)
    result = {'categories': categories, 'law': None, 'law_error': None,
              'remote': [], 'remote_errors': [], 'routing_notes': [], 'external_sent': False, 'connection_attempted': False,
              'description': '질문 키워드 기반 검색 계획 · 실제 조회 결과만 제공 (법적 판단 아님)'}
    # Law MCP operates on this PC; no uploaded documents are used or sent.
    if law_title or wants_law_research(question):
        try: result['law'] = run_law_research(root, question, law_name=law_title)
        except Exception: result['law_error'] = '법제처 MCP 법령 조회 실패 (재확인 필요)'
    if not external_consent:
        result['routing_notes'].append('외부 MCP 전송 동의/자동 호출 설정이 비활성화되어 있습니다.')
        return result
    if not public_search_question(question):
        result['routing_notes'].append('개인정보 또는 내부자료로 의심되는 질문은 외부 MCP로 자동 전송하지 않았습니다. 공개정보만으로 질문을 바꿔주세요.')
        return result
    if not categories:
        result['routing_notes'].append('질문에서 지원되는 검색 분류를 인식하지 못했습니다. 통계·계약·법령 등 검색 목적을 명시해 주세요.')
        return result
    matches = [r for r in effective_connections(root) if r.get('enabled')
               and r.get('scope') in ('both', scope) and r.get('category') in categories]
    if not matches:
        result['routing_notes'].append('질문 분류에 대응하는 활성화된 외부 MCP가 없습니다. 관리자에서 연결 분류·사용 범위·승인 도구를 확인해 주세요.')
    calls_remaining = 8  # Hard cap for both multi-step and other automatic calls.
    for record in matches:
        if calls_remaining <= 0:
            result['routing_notes'].append('한 질문의 외부 MCP 자동 호출은 최대 8회로 제한됩니다.')
            break
        phase = '도구 목록 조회'
        try:
            result['connection_attempted'] = True
            tools = discover(root, record['id'], bearer=read_bearer(root, record['id']))
            if is_trusted_builtin(record) and record.get('category') == 'statistics' and any(
                    t.get('name') == 'kosis_get_data' for t in tools):
                # A chain counts as multiple calls; it never consumes unobserved IDs.
                result['external_sent'] = True
                remaining = min(6, calls_remaining)
                def chained_call(tool_name, arguments):
                    return invoke_arguments(root, record, tool_name, arguments,
                                            bearer=read_bearer(root, record['id']))
                phase = 'KOSIS 다단계 도구 실행'
                chain = chain_kosis(question, tools, chained_call, max_calls=remaining)
                calls_remaining -= len(chain['steps'])
                result['remote'].append({'service':record['name'], 'category':record['category'],
                                         'tool':'KOSIS 다단계 조회', 'result':chain,
                                         'provider':record['url'].split('/')[2],
                                         'tool_returned':chain['status']=='data_returned',
                                         'evidence':[]})
                if chain['status']!='data_returned':
                    result['remote_errors'].append(record['name']+': '+chain['reason'])
                continue
            eligible = []
            for info in tools:
                name = info.get('name', '')
                schema = info.get('input_schema', {})
                approved = name in record.get('tools', []) or (is_trusted_builtin(record) and safe_auto_tool_name(name))
                if (approved and safe_auto_tool_name(name)
                        and _query_arguments(schema, question)):
                    eligible.append(info)
            # Rank search-like tools; do not blindly call the first listed tools.
            eligible.sort(key=lambda meta: (-score_tool(question, meta), meta.get('name','')))
            eligible = [meta for meta in eligible if score_tool(question, meta) > 0]
            for info in eligible[:min(2, calls_remaining)]:
                calls_remaining -= 1
                # The question may be transmitted even if the remote subsequently raises.
                result['external_sent'] = True
                phase = 'MCP 도구 실행'
                output = invoke(root, record, info['name'], question, info['input_schema'],
                                bearer=read_bearer(root, record['id']))
                result['remote'].append({'service': record['name'], 'category': record['category'],
                                         'tool': info['name'], 'result': output,
                                         'provider': record['url'].split('/')[2],
                                         'tool_returned': bool(output.get('ok')),
                                         'evidence': extract_evidence(output.get('data'), record['url'].split('/')[2])})
                result['external_sent'] = True
            if not eligible:
                result['remote_errors'].append(record['name'] + ': 자동 호출 가능한 조회 도구 없음 (필수 입력값·도구 스키마 확인 필요)')
        except (RuntimeError, ValueError, OSError) as exc:
            # Error from the vetted MCP adapter is a fixed, credential-free diagnostic.
            result['remote_errors'].append(record['name'] + f': {phase} 실패 · ' + str(exc)[:150] + ' (실호출 미확인)')
    return result


def render_public_evidence(result: dict, *, include_law: bool = False) -> None:
    """UI presentation; legal law section is rendered by existing trusted views."""
    import streamlit as st
    if not result: return
    st.subheader('🌐 공공데이터 MCP 검색 결과')
    st.caption('검색 분류: ' + (', '.join(result['categories']) or '분류 없음') +
               ' · MCP 연결 ' + ('시도' if result.get('connection_attempted') else '미시도') +
               ' · 질문 전송 ' + ('시도 (실호출 성공 미확인)' if result['external_sent'] else '미시도'))
    if result.get('law_error'): st.warning(result['law_error'])
    if include_law and result.get('law'):
        laws = result['law']
        with st.expander('국가법령정보 MCP 근거 후보', expanded=True):
            for law in laws.get('laws', []):
                st.write('**'+str(law.get('name') or law.get('query', '검색 후보'))+'** · '+str(law.get('status', '미확인')))
                st.caption('시행일: ' + str(law.get('effective_date') or '미확인'))
                if law.get('url', '').startswith('https://'): st.link_button('법령 원문',law['url'])
                for article in law.get('articles', [])[:5]:
                    st.text(str(article.get('title', ''))[:200] + ': ' + str(article.get('content', ''))[:700])
            st.warning(laws.get('caution', '법적 적용 여부 미확인'))
    for item in result['remote']:
        status = 'MCP 도구 응답 반환' if item['tool_returned'] else '오류 응답'
        with st.expander(f"{item['service']} · {item['tool']} · {status}", expanded=True):
            st.caption('출처 서버: ' + item['provider'] + ' · MCP 도구 응답과 원천 API 조회 성공은 구별해야 합니다.')
            for evidence in item.get('evidence', []):
                st.text(evidence['title']+' · 제공기관: '+evidence['source']+' · 기준시점: '+evidence['reference_date'])
                if evidence['url']:
                    st.link_button('원문 확인', evidence['url'])
            if item.get('evidence'):
                st.caption('원문 확인 전 · 데이터 적용성/정확성 미검증')
            with st.expander('반환 원본 구조 확인'):
                st.json(item['result'])
    for note in result.get('routing_notes', []): st.info(note)
    for warning in result['remote_errors']: st.warning(warning)
    if not result['remote'] and not result.get('law') and not result.get('routing_notes'):
        st.info('이번 질문에서 검색 근거자료를 확보하지 못했습니다. MCP 연결 상태·승인 도구·입력 항목을 확인하세요.')
    st.caption('도구 호출 성공은 사업 적법성 또는 데이터 최신성·적용 가능성의 증명이 아닙니다.')

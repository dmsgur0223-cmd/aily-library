"""AILY 4.8.0 WEB — anonymous, per-session, institution-neutral workspace.

Launch: streamlit run web_app.py
No legacy corporation dataset or secrets are loaded by this entry point.
"""
from __future__ import annotations
import os
from pathlib import Path
import streamlit as st

from aily.generic_workspace import MAX_DOCS, MAX_FILE_BYTES, InstitutionDocument, parse_document
from aily.legal_review import LawEvidence, build_packet, render_evidence_text
from aily.law_api import search_laws, law_articles, compare_old_new, LawAPIError
from aily.ai_reviewer import generate_draft, AIReviewError
from aily.public_research import run_public_research, render_public_evidence
from aily.remote_mcp import public_search_question

VERSION = '4.96'


def _server_secret(name: str) -> str:
    """Never look inside local config/ or ship credentials to the browser."""
    value = os.environ.get(name, '').strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, '')).strip()
    except (FileNotFoundError, KeyError, AttributeError):
        return ''


def _setup() -> None:
    if 'workspace_docs' not in st.session_state:
        st.session_state.workspace_docs = []
    if 'selected_laws' not in st.session_state:
        st.session_state.selected_laws = []
    if 'workspace_institution' not in st.session_state:
        st.session_state.workspace_institution = ''


def render_documents() -> None:
    st.header('내 기관 자료')
    st.info('문서는 업로드만으로 지식베이스에 적용되지 않습니다. 텍스트 추출을 확인하고 적용을 누른 뒤 이 브라우저 세션에서만 검색됩니다.')
    st.warning('로그인 없는 공개 시연 환경입니다. 개인정보·비공개 기관 문서·기밀자료는 업로드하지 마세요.')
    institution = st.text_input('기관명 (화면 표시용)', value=st.session_state.workspace_institution,
                                max_chars=100, placeholder='예: ○○문화재단', key='institution_input')
    if institution != st.session_state.workspace_institution:
        st.session_state.workspace_institution = institution
        st.session_state.pop('web_review_packet', None)
        st.session_state.pop('web_ai_draft', None)
    files = st.file_uploader('업무 규정·정관·전결규정 (최대 10개, 각 8MB)',
                             type=['txt', 'md', 'pdf', 'docx', 'hwp', 'hwpx'], accept_multiple_files=True)
    revision = st.text_input('자료 기준일 (선택, YYYY-MM-DD)', placeholder='2026-10-30', max_chars=10)
    if st.button('1. 업로드 문서의 텍스트 추출 미리보기', disabled=not bool(files)):
        if len(files) > MAX_DOCS:
            st.error('한 번에 최대 10개까지 업로드할 수 있습니다.')
        else:
            staged = []
            errors = []
            for uploaded in files:
                if uploaded.size > MAX_FILE_BYTES:
                    errors.append(uploaded.name + ': 8MB 초과')
                    continue
                try:
                    staged.append(parse_document(uploaded.name, uploaded.getvalue(), revision.strip()))
                except ValueError as exc:
                    errors.append(uploaded.name + ': ' + str(exc))
            st.session_state.pending_docs = staged
            st.session_state.pending_errors = errors
    for error in st.session_state.get('pending_errors', []):
        st.error(error)
    pending = st.session_state.get('pending_docs', [])
    if pending:
        st.subheader('추출 내용 확인 (아직 미적용)')
        for doc in pending:
            with st.expander(f'{doc.name} · {len(doc.passages)}개 발췌', expanded=False):
                st.text('\n\n'.join(x.text[:600] for x in doc.passages[:3])[:2500])
                st.caption('스캔문서/표 구조/문서 효력 및 기준일은 자동 검증되지 않습니다.')
        agree = st.checkbox('문서 내용을 확인했으며 이 세션의 검색 자료로 사용합니다.', key='agree_to_session_docs')
        if st.button('2. 확인한 문서를 이 세션에 적용', type='primary', disabled=not agree):
            old = {d.digest: d for d in st.session_state.workspace_docs}
            for doc in pending:
                old[doc.digest] = doc
            if len(old) > MAX_DOCS:
                st.error('기존 자료를 포함해 최대 10개까지만 적용할 수 있습니다.')
            else:
                st.session_state.workspace_docs = list(old.values())
                st.session_state.pop('web_review_packet', None)
                st.session_state.pop('web_ai_draft', None)
                st.session_state.pending_docs = []
                st.session_state.pending_errors = []
                st.success('현재 브라우저 세션에만 적용했습니다. 서버 공유 DB/임베딩에는 저장하지 않았습니다.')
                st.rerun()
    st.divider()
    st.subheader('현재 세션에 적용된 자료')
    if not st.session_state.workspace_docs:
        st.caption('등록된 기관 자료가 없습니다. 다른 기관의 규정은 자동으로 제공되지 않습니다.')
    for doc in st.session_state.workspace_docs:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.write(f'**{doc.name}** · {len(doc.passages)}단락 · 기준일 {doc.declared_date or "미입력"}')
        with c2:
            if st.button('제외', key=f'remove_{doc.digest[:12]}'):
                st.session_state.workspace_docs = [d for d in st.session_state.workspace_docs if d.digest != doc.digest]
                st.session_state.pop('web_review_packet', None)
                st.session_state.pop('web_ai_draft', None)
                st.rerun()


def render_law() -> None:
    st.header('국가법령정보')
    st.caption('법제처 국가법령정보 OPEN API 실시간 REST 조회. 검색 결과의 법령·조문은 이용자가 선택해야 업무 검토에 반영됩니다.')
    oc = _server_secret('AILY_LAW_OC')
    if not oc:
        st.warning('서버에 국가법령정보 OC가 설정되지 않았습니다. 운영자가 호스팅 Secret `AILY_LAW_OC`을 설정해야 실제 조회할 수 있습니다.')
    with st.form('law_search'):
        query = st.text_input('법령명', max_chars=80, placeholder='예: 지방공기업법')
        requested = st.form_submit_button('실제 법령 검색', disabled=not bool(oc))
    if requested:
        try:
            st.session_state.web_law_results = search_laws(oc, query, limit=15)
            st.session_state.web_law_error = ''
            st.session_state.pop('web_law_detail', None)
            st.session_state.pop('web_law_comparison',None)
        except (ValueError, LawAPIError) as exc:
            st.session_state.web_law_error = str(exc)
            st.session_state.web_law_results = []
    if st.session_state.get('web_law_error'):
        st.error(st.session_state.web_law_error)
    for result in st.session_state.get('web_law_results', []):
        with st.container(border=True):
            st.write(f'**{result.name}** · 시행일 {result.effective_date or "미확인"}')
            st.caption('공포·개정일: '+(result.promulgation_date or '미확인')+' · 제·개정: '+(result.revision_type or '미확인'))
            st.caption(f'소관부처 {result.ministry or "미확인"} · API 검색 결과 (법적 적용 여부 미판정)')
            if result.detail_link:
                st.link_button('국가법령정보 원문', result.detail_link)
            if st.button('개정 전·후 비교',key='compare_'+(result.mst or result.law_id)):
                try:
                    st.session_state.web_law_comparison = (result.name,compare_old_new(oc,law_id=result.law_id,mst=result.mst))
                except (ValueError,LawAPIError) as exc:
                    st.error('신구법 API 조회 실패: '+str(exc)[:160])
            if st.button('조문 조회', key='get_' + (result.law_id or result.mst)):
                try:
                    detail = law_articles(oc, result.law_id, mst=result.mst)
                    st.session_state.web_law_detail = (result, detail)
                except (ValueError, LawAPIError) as exc:
                    st.error(str(exc))
    comparison=st.session_state.get('web_law_comparison')
    if comparison:
        title,delta=comparison
        st.subheader('개정 전·후 조문 비교 · '+title)
        if not delta.get('available'):
            st.warning(delta.get('message','공식 비교 결과 없음'))
        else:
            st.caption('이전 공포일 '+str(delta.get('old',{}).get('promulgation_date') or '미확인')+' · 새 공포일 '+str(delta.get('new',{}).get('promulgation_date') or '미확인')+' · 새 시행일 '+str(delta.get('new',{}).get('effective_date') or '미확인'))
            for ch in delta['changes']:
                with st.expander(ch['article']+' · '+ch['type']):
                    st.write(ch.get('summary',''))
                    c1,c2=st.columns(2)
                    with c1:st.text('개정 전\n'+ch['before'])
                    with c2:st.text('개정 후\n'+ch['after'])
            if delta.get('truncated'):st.warning('최대 20건 표시. 전체 변경은 국가법령정보센터에서 확인하세요.')
            st.info(delta['note'])
    detail = st.session_state.get('web_law_detail')
    if detail:
        law, data = detail
        st.divider()
        st.subheader(f'{data.get("title") or law.name} 조문 (실제 API 응답)')
        if not data.get('articles'):
            st.warning('응답에서 조문을 추출하지 못했습니다. 원문 링크에서 직접 확인하세요.')
        for i, article in enumerate(data.get('articles', [])[:80]):
            raw = article.get('content', '')
            heading = article.get('title') or raw[:48] or f'조문 {i + 1}'
            with st.expander(f'{i+1}. {heading[:80]}'):
                st.text(raw[:4500])
                if st.button('이 조문을 검토 근거에 추가', key=f'select_article_{law.law_id}_{i}'):
                    selected = LawEvidence(law.name, law.law_id or law.mst, law.effective_date,
                                           heading, raw[:4500], law.detail_link)
                    present = st.session_state.selected_laws
                    if any(x.identifier == selected.identifier and x.article == selected.article for x in present):
                        st.info('이미 추가한 조문입니다.')
                    elif len(present) >= 12:
                        st.error('조문 근거는 최대 12건까지 선택할 수 있습니다.')
                    else:
                        st.session_state.selected_laws.append(selected)
                        st.session_state.pop('web_review_packet', None)
                        st.session_state.pop('web_ai_draft', None)
                        st.success('현재 세션의 검토 근거에 추가했습니다.')
    st.divider()
    st.subheader(f'선택된 법령 조문: {len(st.session_state.selected_laws)}건')
    for i, law in enumerate(st.session_state.selected_laws):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f'{law.name} · {law.article} · 시행일 {law.effective_date or "미확인"}')
        with col2:
            if st.button('제외', key=f'exclude_law_{i}'):
                st.session_state.selected_laws.pop(i)
                st.session_state.pop('web_review_packet', None)
                st.session_state.pop('web_ai_draft', None)
                st.rerun()


def render_assistant() -> None:
    st.header('지방공기업 업무지원')
    st.caption('기관별 내규 + 직접 선택한 국가법령 조문을 함께 제시합니다. 자동으로 위법 여부나 결재권자를 확정하지 않습니다.')
    st.write(f'**현재 기관:** {st.session_state.workspace_institution or "미지정"} · '
             f'**적용 내규:** {len(st.session_state.workspace_docs)}개 · '
             f'**선택 법령 조문:** {len(st.session_state.selected_laws)}개')
    with st.form('review_question'):
        question = st.text_area('업무 질문', placeholder='예: 행사 물품구매 시 계약 및 결재 기준은?', max_chars=500)
        submitted = st.form_submit_button('등록 근거로 검토', type='primary')
    if submitted:
        try:
            packet = build_packet(st.session_state.workspace_institution, question,
                                  st.session_state.workspace_docs, st.session_state.selected_laws)
            st.session_state.web_review_packet = packet
            st.session_state.pop('web_ai_draft', None)
            st.session_state.pop('web_public_result',None)
            if public_search_question(question):
                # Only typed public question; no institution uploads or prepared packet leave the session.
                st.session_state.web_public_result = run_public_research(
                    Path(__file__).resolve().parent, question, 'corp', external_consent=True)
            else:
                st.session_state.web_public_result = {'blocked':True}
        except ValueError as exc:
            st.error(str(exc))
    remote = st.session_state.get('web_public_result')
    if isinstance(remote,dict) and remote.get('blocked'):
        st.warning('내부·개인정보로 의심되는 질문은 외부 MCP에 자동 전송하지 않았습니다.')
    elif remote:
        render_public_evidence(remote)
    packet = st.session_state.get('web_review_packet')
    if packet:
        st.subheader('기관 자료 근거')
        if not packet.internal:
            st.warning('질문과 일치하는 기관 내부 규정 근거를 찾지 못했습니다.')
        for i, passage in enumerate(packet.internal, 1):
            with st.expander(f'[내규 {i}] {passage.document} · {passage.location}', expanded=(i <= 2)):
                st.text(passage.excerpt)
        st.subheader('선택한 법령 근거')
        if not packet.laws:
            st.warning('국가법령 조문이 선택되지 않았습니다. 법령 검증을 마친 것이 아닙니다.')
        for i, law in enumerate(packet.laws, 1):
            with st.expander(f'[법령 {i}] {law.name} · {law.article}'):
                st.caption('시행일: ' + (law.effective_date or '미확인'))
                st.text(law.text[:2500])
                if law.url:
                    st.link_button('원문 열기', law.url)
        for warning in packet.cautions:
            st.info(warning)
        st.download_button('근거 검토 텍스트 다운로드', render_evidence_text(packet),
                           file_name='AILY_근거검토.txt', mime='text/plain')
        st.divider()
        st.subheader('AI 보조 비교 초안 (선택)')
        st.caption('AI를 사용하지 않아도 근거 검색은 동작합니다. AI 초안은 최종 법률 판단이 아닙니다.')
        key = _server_secret('AILY_OPENAI_API_KEY')
        if not key:
            st.caption('서버에 OpenAI API 인증값이 없어 AI 요약을 실행할 수 없습니다.')
        st.warning('AI 실행 시 질문과 화면에 표시된 발췌문·선택 조문이 외부 AI API로 전송됩니다. 내부자료 전송이 허용된 경우에만 사용하세요.')
        consent = st.checkbox('발췌 근거와 질문을 외부 AI로 전송하는 데 동의합니다.', key='ai_send_consent')
        if st.button('AI 비교 초안 생성 (외부 API 실제 호출)', disabled=not (consent and bool(key) and (packet.internal or packet.laws))):
            try:
                model = _server_secret('AILY_OPENAI_MODEL') or 'gpt-4.1-mini'
                st.session_state.web_ai_draft = generate_draft(packet, key, model=model)
            except (ValueError, AIReviewError) as exc:
                st.error(str(exc))
        if st.session_state.get('web_ai_draft'):
            st.success('AI API가 응답한 초안입니다. 근거 조문 및 법령 적용 여부는 담당자 확인이 필요합니다.')
            st.write(st.session_state.web_ai_draft)


def render_admin() -> None:
    st.header('관리자 · 공개 운영 화면')
    st.caption('로그인 없이 접근할 수 있도록 요청된 공개 상태 페이지입니다. 서버 전체 설정을 바꾸는 기능은 제공하지 않습니다.')
    st.metric('AILY 웹 버전', VERSION)
    st.write('**연결 준비 상태** (설정 여부만 표시하며, 실시간 API 성공 여부는 아닙니다)')
    st.write('국가법령정보 OC: ' + ('설정됨 · 실제 호출 미검증' if _server_secret('AILY_LAW_OC') else '미설정'))
    st.write('OpenAI API: ' + ('설정됨 · 실제 호출 미검증' if _server_secret('AILY_OPENAI_API_KEY') else '미설정'))
    st.divider()
    st.write('**이 브라우저 세션의 자료 관리**')
    st.write(f'기관 자료 {len(st.session_state.workspace_docs)}건 / 선택 법령 {len(st.session_state.selected_laws)}건')
    if st.button('내 세션에 적용한 자료와 선택 조문 모두 초기화'):
        st.session_state.workspace_docs = []
        st.session_state.selected_laws = []
        st.session_state.pending_docs = []
        st.session_state.pop('web_review_packet', None)
        st.session_state.pop('web_ai_draft', None)
        st.success('현재 세션의 자료만 초기화했습니다.')
        st.rerun()
    st.info('다른 이용자의 세션, 서버 인증값, 원본 소스, 배포 설정은 이 페이지에서 읽거나 변경할 수 없습니다.')


def main() -> None:
    st.set_page_config(page_title='AILY 2.0 WEB | 지방공기업 업무지원', page_icon='🏢', layout='wide')
    _setup()
    with st.sidebar:
        st.title('🏢 AILY 2.0 WEB')
        st.caption(f'기관 중립형 업무비서 · v{VERSION}')
        page = st.radio('메뉴', ['지방공기업 업무지원', '법령 확인', '내 기관 자료', '관리자 · 공개', '도서 검토 및 선정 지원'], label_visibility='collapsed')
        st.divider()
        st.caption('이용자별 임시 세션 · 자료 자동 학습/공유 없음')
        st.warning('공개 시연: 개인정보 및 비공개 공문·내규는 업로드 금지')
    if page == '지방공기업 업무지원':
        render_assistant()
    elif page == '내 기관 자료':
        render_documents()
    elif page == '법령 확인':
        render_law()
    elif page == '도서 검토 및 선정 지원':
        from aily.book_review_ui import render_book_review
        render_book_review(_server_secret('AILY_YES24_API_KEY'), _server_secret('AILY_QNET_API_KEY'))
    elif page == '관리자 · 공개':
        render_admin()


if __name__ == '__main__':
    main()

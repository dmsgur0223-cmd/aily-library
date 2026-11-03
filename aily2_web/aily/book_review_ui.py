"""Public-web, session-only 희망도서 검토 (no corporation-specific defaults or stored secrets)."""
from __future__ import annotations
from datetime import date
import hashlib

import pandas as pd
import streamlit as st

from .books import load_candidates, load_holdings, review_requests, export_results, prepare_general_candidates
from .book_ai import apply_yes24_lookup
from .book_batch import run_batches
from .book_filters_ui import render_filter_settings
from .qualifications import ensure_qualification_cache


def render_book_review(yes24_key: str, qnet_key: str):
    st.header('도서 검토 및 선정 지원')
    st.caption('도서관 전문업무 보조 · 1차 기준 선택 · 2차 자료유형 선택 · 최종 판단은 담당사서')
    st.warning('공개 웹 환경입니다. 신청자 개인정보 및 비공개 기관자료가 포함된 파일은 업로드하지 마세요.')
    purchase_type=st.selectbox('도서 구입 유형', ['희망도서','정기도서','기타 도서 구입'], key='web_book_purchase_type')
    if purchase_type!='희망도서':
        st.info('정기·기타 구입 도서는 신청자별 월 권수·중복 신청 규칙을 사용하지 않습니다. 기관별 선정 기준은 직접 선택하며 최종 판단은 담당자가 확인합니다.')
    settings = render_filter_settings('web_book', allow_private_checks=False)
    st.caption('**필터 OFF**는 해당 기준으로 제외하지 않는다는 뜻입니다. 최종 구매 적격 판정이 아닙니다.')
    holdings = None
    holdings_file = None
    if settings.holdings_enabled:
        holdings_file = st.file_uploader('구립도서관 통합 소장목록 (선택 · ISBN/소장도서관)', type=['xlsx'], key='web_books_holdings')
        if holdings_file is not None and holdings_file.size <= 15_000_000:
            try:
                holdings = load_holdings(holdings_file.getvalue())
            except (ValueError, OSError, TypeError) as exc:
                st.error('통합 소장목록 오류: '+str(exc)[:180])
    whole_scope = False
    if settings.cross_library_duplicate_enabled or settings.monthly_limit_enabled:
        whole_scope = st.checkbox('업로드된 신청 자료가 전체 대상 도서관의 당월 내역임을 확인', value=False, key='web_books_scope')
    whole_holdings = False
    if settings.holdings_enabled:
        whole_holdings = st.checkbox('소장자료가 전체 대상 도서관의 내역임을 확인', value=False, key='web_holdings_scope')
    upload = st.file_uploader('도서 검토 목록 엑셀 (.xlsx, 최대 15MB)', type=['xlsx'], key='web_books_upload')
    if upload is None:
        st.info('이용기관의 신청 목록을 업로드해 주세요. 도서관명은 특정 공단의 목록으로 제한하지 않습니다.')
        return
    if upload.size > 15_000_000:
        st.error('15MB 이하 파일만 올릴 수 있습니다.')
        return
    file_data = upload.getvalue()
    signature = (purchase_type,hashlib.sha256(file_data).hexdigest(), settings, whole_scope, whole_holdings,
                 hashlib.sha256(holdings_file.getvalue()).hexdigest() if holdings_file is not None else '')
    if st.session_state.get('web_books_signature') != signature:
        st.session_state.web_books_signature = signature
        st.session_state.pop('web_books_results', None)
    try:
        source = load_candidates(file_data)
        if len(source) > 5000:
            st.error('한 번에 최대 5,000건까지만 검토할 수 있습니다.')
            return
        review_input, exclusions = prepare_general_candidates(source)
    except (ValueError, TypeError, OSError, ImportError) as exc:
        st.error('엑셀 읽기 실패: ' + str(exc)[:180])
        return
    st.caption(f'업로드 {len(source)}건 · 검토 대상 {len(review_input)}건 · 취소·반려 {exclusions.get("취소·반려 제외",0)}건')
    if st.button('① 설정한 기준으로 1차 검토', type='primary', use_container_width=True):
        st.session_state.web_books_results = review_requests(source, holdings=holdings, complete_monthly_data=whole_scope,
                                                          complete_holdings_data=whole_holdings,
                                                          today=date.today(), settings=settings)
    results = st.session_state.get('web_books_results')
    if results is None:
        return
    if results.empty:
        st.warning('검토 대상 도서가 없습니다.')
        return
    first_ok = results['1차판정'].eq('1차 필터링 통과')
    good, failed = int(first_ok.sum()), int((~first_ok).sum())
    c1, c2 = st.columns(2)
    c1.metric('1차 검토 통과', good)
    c2.metric('1차 통과 안 됨/자료 보완', failed)
    st.dataframe(results[['서명','발행년','가격','1차판정','판정사유','추가확인']],
                 hide_index=True, use_container_width=True)

    if settings.second_enabled:
        st.subheader('② ISBN 서지정보·선택 유형 검사')
        st.caption('YES24 상품 상세 API로 ISBN 확인 후 활성화된 제외 유형만 판정합니다.')
        remaining = results.index[first_ok & results['2차판정'].eq('미실행')]
        st.caption(f'2차 미처리 {len(remaining)}권 · 선택 항목: {", ".join(settings.second_categories)}')
        st.caption('전체 일괄 검사는 내부적으로 15권씩 나눠 실행합니다. 중단 시 완료된 묶음은 세션에 남습니다.')
        qnet_needed = bool(set(settings.second_categories) & {'수험서·자격증 교재','자격증 교재'})
        if not yes24_key:
            st.warning('서버에 YES24 인증키 `AILY_YES24_API_KEY`를 등록해야 2차 조회를 실행할 수 있습니다.')
        if qnet_needed and not qnet_key:
            st.warning('「자격증 교재」 검사를 위해 서버의 Q-Net 인증키 `AILY_QNET_API_KEY`가 필요합니다. 해당 검사 체크를 해제하면 다른 유형은 진행 가능합니다.')
        ready = bool(yes24_key) and (not qnet_needed or bool(qnet_key))
        if st.button(f'2차 전체 일괄 조회 · {len(remaining)}권', disabled=not ready or not len(remaining),
                     type='primary', use_container_width=True):
            names = None
            if qnet_needed:
                if 'web_book_qnet_names' not in st.session_state:
                    try:
                        names, _ = ensure_qualification_cache(qnet_key)
                        st.session_state.web_book_qnet_names = names
                    except (RuntimeError, ValueError, OSError) as exc:
                        st.error('Q-Net 실제 조회 실패: '+str(exc)[:150])
                        names = None
                else:
                    names = st.session_state.web_book_qnet_names
            if not qnet_needed or names:
                bar = st.progress(0, text='전체 ISBN 조회 중')
                results = run_batches(results, remaining, yes24_key, progress=bar.progress,
                                      qualifications=names, categories=settings.second_categories,
                                      checkpoint=lambda part: st.session_state.update(web_books_results=part))
                st.session_state.web_books_results = results
                st.rerun()
        st.caption('서지정보 출처: YES24 · 상세 상품정보를 표시할 때는 상품 링크도 함께 제공합니다.')
        st.dataframe(results[['서명','ISBN','2차판정','2차근거','YES24상품링크']], hide_index=True, use_container_width=True)
    else:
        st.info('2차 유형 검사는 사용자 설정으로 생략했습니다.')

    st.subheader('③ 결과 다운로드')
    st.caption('검토 결과에는 신청자 성명, 회원번호, 연락처 등의 원본 개인정보를 포함하지 않습니다.')
    st.download_button('현재 기준 및 검토 결과 엑셀 다운로드',
                       data=export_results(results, {'검토 유형':purchase_type,'검토 기준일':date.today().isoformat(),
                                                     '검토 건수':len(results), '최종 선정':'담당자 판단'}, settings),
                       file_name='AILY_도서구입검토.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       use_container_width=True)

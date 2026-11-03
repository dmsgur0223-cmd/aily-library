"""Shared Streamlit controls for institution-configurable book screening.

The defaults describe the existing AILY example, not a universal policy.
No values are written to files or across users.
"""
from __future__ import annotations
import streamlit as st
from .books import BookFilterSettings

from .qualifications import SECOND_FILTER_CATEGORIES, DEFAULT_SECOND_CATEGORIES
CATEGORY_ORDER = SECOND_FILTER_CATEGORIES


def render_filter_settings(prefix: str, *, allow_private_checks: bool = True) -> BookFilterSettings:
    st.subheader('선정 검토 기준 설정')
    st.caption('현재 작업에만 적용하는 선택형 기준입니다. 기관별 공식 선정규정으로 자동 확정되지 않습니다.')
    with st.container(border=True):
        price_enabled = st.toggle('가격 기준 적용', value=True, key=f'{prefix}_price_on')
        price_limit = int(st.number_input('정가 상한 (원)', min_value=0, max_value=10_000_000,
                                          step=1000, value=30_000, disabled=not price_enabled,
                                          key=f'{prefix}_price_limit'))
        st.divider()
        year_enabled = st.toggle('발행일 기준 적용', value=True, key=f'{prefix}_year_on')
        yrs = int(st.number_input('발행 후 허용 기간 (년)', min_value=0, max_value=100,
                                  step=1, value=5, disabled=not year_enabled,
                                  key=f'{prefix}_year_limit'))
        month_precision = st.checkbox('월 단위까지 세부 설정', value=False,
                                      disabled=not year_enabled, key=f'{prefix}_month_mode')
        months = int(st.number_input('추가 허용 기간 (개월)', min_value=0, max_value=11,
                                     step=1, value=0, disabled=not (year_enabled and month_precision),
                                     key=f'{prefix}_extra_months'))
        if year_enabled and month_precision:
            st.caption('발행월을 알 수 없는 경계 연도 자료는 자동 통과/제외하지 않고 확인 대상으로 표시합니다.')
        st.divider()
        st.markdown('**구립도서관 전체 신청·소장 확인 (선택)**')
        duplicate_enabled = st.checkbox('구립도서관 간 동일 신청자·ISBN 중복 신청 검사', value=False, disabled=not allow_private_checks,
                                        key=f'{prefix}_duplicate_on')
        monthly_enabled = st.checkbox('구립도서관 통합 월 신청권수 제한 검사', value=False, disabled=not allow_private_checks,
                                      key=f'{prefix}_monthly_on')
        monthly_count = int(st.number_input('신청자별 월 최대 권수', min_value=1, max_value=100, value=2,
                            disabled=not monthly_enabled, key=f'{prefix}_monthly_limit'))
        holdings_enabled = st.checkbox('구립도서관 전체 소장 여부 검사 (통합 소장목록 업로드)', value=False,
                                       key=f'{prefix}_holdings_on')
        holdings_count = int(st.number_input('제외 기준 소장 도서관 수', min_value=1, max_value=100, value=4,
                              disabled=not holdings_enabled, key=f'{prefix}_holdings_limit'))
        if not allow_private_checks:
            st.caption('공개 웹 환경에서는 신청자 식별정보를 사용하는 중복 신청·월 권수 검사를 지원하지 않습니다. 로컬 설치본에서만 사용하세요.')
        if duplicate_enabled or monthly_enabled:
            st.caption('신청자번호·신청일시·도서관명이 있는 파일에서만 검사합니다. 다른 도서관 자료가 빠져 있으면 전체 확인으로 간주하지 않습니다.')
        if holdings_enabled:
            st.caption('별도 통합 소장목록의 ISBN·소장도서관 기준입니다. 실시간 전체 관 소장 API를 조회하는 기능은 아닙니다.')
        second_enabled = st.checkbox('2차 서지정보·자료유형 검사 사용', value=True,
                                     key=f'{prefix}_second_on')
        selected = []
        st.caption('2차 탈락 근거로 검사할 유형을 선택하세요. 8개 중 기본 7개 ON, 만화류 OFF입니다.')
        cols = st.columns(3)
        for i, category in enumerate(CATEGORY_ORDER):
            with cols[i % 3]:
                if st.checkbox(category, value=category in DEFAULT_SECOND_CATEGORIES, disabled=not second_enabled,
                               key=f'{prefix}_cat_{i}'):
                    selected.append(category)
        if second_enabled and not selected:
            st.warning('선택한 2차 검사 유형이 없어 2차 검사는 실행되지 않습니다.')
    return BookFilterSettings(
        price_enabled=price_enabled, price_limit=price_limit,
        year_enabled=year_enabled, max_age_years=yrs,
        month_precision=year_enabled and month_precision,
        extra_months=months if (year_enabled and month_precision) else 0,
        cross_library_duplicate_enabled=duplicate_enabled and allow_private_checks,
        monthly_limit_enabled=monthly_enabled and allow_private_checks, monthly_limit_count=monthly_count,
        holdings_enabled=holdings_enabled, holdings_limit=holdings_count,
        second_enabled=second_enabled and bool(selected),
        second_categories=tuple(c for c in CATEGORY_ORDER if c in selected) if second_enabled else (),
    )

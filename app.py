import streamlit as st
import pandas as pd
import random

# =========================================================
# 1. 기본 설정
# =========================================================
st.set_page_config(
    page_title="Aily 도서 추천",
    page_icon="🐰",
    layout="centered"
)

# =========================================================
# 2. CSS 디자인
# =========================================================
st.markdown("""
<style>

    /* 전체 배경 */
    .stApp {
        background: linear-gradient(
            180deg,
            #f8f6ff 0%,
            #ffffff 45%,
            #faf9ff 100%
        );
    }

    /* 상단 여백 */
    .block-container {
        max-width: 850px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* 제목 */
    .main-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 800;
        color: #4b3f72;
        margin-top: 0.5rem;
        margin-bottom: 0.3rem;
    }

    .sub-title {
        text-align: center;
        color: #77718b;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    /* 안내 박스 */
    .intro-box {
        background: white;
        border-radius: 20px;
        padding: 22px 25px;
        margin: 20px 0 25px 0;
        border: 1px solid #ebe7f5;
        box-shadow: 0 5px 20px rgba(90, 70, 130, 0.06);
        text-align: center;
    }

    .intro-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #51456f;
        margin-bottom: 7px;
    }

    .intro-text {
        color: #777;
        font-size: 0.95rem;
    }

    /* 추천 결과 제목 */
    .recommend-title {
        background: linear-gradient(135deg, #6f5aa8, #8b78c6);
        color: white;
        border-radius: 16px;
        padding: 15px 20px;
        margin: 25px 0 15px 0;
        font-size: 1.15rem;
        font-weight: 700;
        box-shadow: 0 5px 15px rgba(111, 90, 168, 0.18);
    }

    /* 책 카드 */
    .book-card {
        background: white;
        border-radius: 18px;
        padding: 20px 22px;
        margin: 14px 0;
        border: 1px solid #ebe8f2;
        box-shadow: 0 5px 18px rgba(60, 50, 90, 0.07);
    }

    .book-number {
        display: inline-block;
        background: #eeeafd;
        color: #6857a0;
        border-radius: 20px;
        padding: 4px 11px;
        font-size: 0.8rem;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .book-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: #302b3d;
        margin-bottom: 12px;
    }

    .book-info {
        color: #686474;
        font-size: 0.92rem;
        line-height: 1.8;
    }

    .call-number {
        background: #f7f5fc;
        border-radius: 10px;
        padding: 8px 12px;
        display: inline-block;
        color: #50447a;
        font-weight: 700;
        margin-top: 5px;
    }

    /* Streamlit 버튼 */
    .stButton > button {
        width: 100%;
        height: 52px;
        border-radius: 14px;
        border: none;
        background: linear-gradient(135deg, #6f5aa8, #8975c2);
        color: white;
        font-size: 1.05rem;
        font-weight: 700;
        box-shadow: 0 5px 15px rgba(111, 90, 168, 0.2);
        transition: 0.2s;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(111, 90, 168, 0.28);
        border: none;
    }

    /* selectbox */
    div[data-baseweb="select"] > div {
        border-radius: 12px;
        border-color: #ddd7ed;
        min-height: 48px;
    }

    /* 구분선 */
    hr {
        border: none;
        height: 1px;
        background: #e9e5f1;
        margin: 25px 0;
    }

    /* 하단 */
    .footer {
        text-align: center;
        color: #aaa5b4;
        font-size: 0.8rem;
        margin-top: 35px;
    }

</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. Aily 이미지
# =========================================================
image_list = ["aily1.png", "aily2.png"]
selected_image = random.choice(image_list)

col1, col2, col3 = st.columns([1, 1.5, 1])

with col2:
    try:
        st.image(selected_image, use_container_width=True)
    except FileNotFoundError:
        st.warning(
            "이미지 파일을 찾을 수 없습니다. "
            "'aily1.png', 'aily2.png' 파일을 확인해주세요."
        )


# =========================================================
# 4. 제목
# =========================================================
st.markdown(
    '<div class="main-title">🐰 심곡도서관 보조사서 Aily</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">AI와 함께 발견하는 나만의 책</div>',
    unsafe_allow_html=True
)


# =========================================================
# 5. 소개 영역
# =========================================================
st.markdown("""
<div class="intro-box">
    <div class="intro-title">📚 어떤 책을 찾고 계신가요?</div>
    <div class="intro-text">
        관심 있는 주제를 선택하면 Aily가 책을 골라드려요.
    </div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 6. 엑셀 데이터 불러오기
# =========================================================
def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)


file_path = "학습데이터.xlsx"


try:
    all_topics_data = load_data(file_path)
    topics = list(all_topics_data.keys())

    # 주제 선택
    selected_topic = st.selectbox(
        "🔎 관심 주제",
        topics
    )

    # 선택된 주제의 책 수 표시
    selected_df = all_topics_data[selected_topic]

    st.caption(
        f"📖 '{selected_topic}' 주제의 도서 "
        f"{len(selected_df):,}권"
    )

    # 추천 버튼
    if st.button(
        f"✨ '{selected_topic}' 도서 추천받기"
    ):

        df = all_topics_data[selected_topic]

        if df.empty:

            st.warning(
                f"앗! '{selected_topic}' 주제에 "
                "추천할 도서가 아직 비어있어요. 😅"
            )

        else:

            num_books = min(3, len(df))
            recommended = df.sample(n=num_books)

            # 추천 완료
            st.markdown(
                f"""
                <div class="recommend-title">
                    🐰 Aily의 '{selected_topic}' 추천 도서
                </div>
                """,
                unsafe_allow_html=True
            )

            # 책 카드
            for book_index, (_, row) in enumerate(
                recommended.iterrows(),
                start=1
            ):

                # 데이터 안전 처리
                def get_value(position):
                    try:
                        value = row.iloc[position]

                        if pd.isna(value):
                            return "정보 없음"

                        return str(value)

                    except (IndexError, KeyError):
                        return "정보 없음"

                reg_number = get_value(0)
                call_number = get_value(1)
                title = get_value(2)
                author = get_value(3)
                publisher = get_value(4)

                st.markdown(
                    f"""
                    <div class="book-card">

                        <div class="book-number">
                            추천 {book_index}
                        </div>

                        <div class="book-title">
                            📖 {title}
                        </div>

                        <div class="book-info">
                            👤 <b>저자</b>　{author}<br>
                            🏢 <b>출판사</b>　{publisher}<br>
                            🔖 <b>등록번호</b>　{reg_number}<br>

                            <div class="call-number">
                                📍 청구기호　{call_number}
                            </div>
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


except FileNotFoundError:

    st.error(
        "📂 엑셀 파일을 찾을 수 없습니다.\n\n"
        "'학습데이터.xlsx' 파일이 앱과 같은 폴더에 있는지 확인해주세요."
    )


# =========================================================
# 7. 하단
# =========================================================
st.markdown(
    """
    <div class="footer">
        심곡도서관 × Aily &nbsp; | &nbsp; AI 북큐레이션
    </div>
    """,
    unsafe_allow_html=True
)

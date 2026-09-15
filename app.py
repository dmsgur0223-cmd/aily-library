import streamlit as st
import pandas as pd
import random
import os

# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="Aily 도서 추천",
    page_icon="🐰",
    layout="centered"
)

# --------------------------------------------------
# CSS 디자인
# --------------------------------------------------

st.markdown("""
<style>

.stApp {
    background: linear-gradient(180deg, #f8f6ff 0%, #ffffff 55%, #faf9ff 100%);
}

.block-container {
    max-width: 850px;
    padding-top: 40px;
    padding-bottom: 50px;
}

/* 메인 제목 */
.main-title {
    text-align: center;
    font-size: 2.1rem;
    font-weight: 800;
    color: #4b3f72;
    margin-top: 10px;
    margin-bottom: 5px;
}

.sub-title {
    text-align: center;
    font-size: 1rem;
    color: #81799a;
    margin-bottom: 25px;
}

/* 메뉴 카드 */
.menu-card {
    background: white;
    border: 1px solid #e7e0f5;
    border-radius: 20px;
    padding: 25px 28px;
    margin-top: 18px;
    margin-bottom: 10px;
    box-shadow: 0 5px 18px rgba(80, 60, 120, 0.07);
}

.menu-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #4b3f72;
    margin-bottom: 12px;
}

.menu-description {
    background: #f7f8fa;
    border-radius: 12px;
    padding: 15px 18px;
    color: #555;
    font-size: 0.95rem;
    line-height: 1.7;
}

/* 버튼 */
.stButton > button {
    width: 100%;
    height: 52px;
    border: none;
    border-radius: 14px;
    background: linear-gradient(135deg, #6f5aa8, #8975c2);
    color: white;
    font-size: 1rem;
    font-weight: 700;
    box-shadow: 0 6px 15px rgba(111, 90, 168, 0.20);
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 9px 20px rgba(111, 90, 168, 0.28);
}

/* 추천 제목 */
.recommend-title {
    background: linear-gradient(135deg, #6f5aa8, #8975c2);
    color: white;
    border-radius: 15px;
    padding: 17px 20px;
    font-size: 1.15rem;
    font-weight: 700;
    margin-top: 15px;
    margin-bottom: 18px;
}

/* 책 카드 */
.book-card {
    background: white;
    border: 1px solid #e8e2f2;
    border-radius: 18px;
    padding: 24px;
    margin: 15px 0;
    box-shadow: 0 5px 18px rgba(70, 50, 100, 0.08);
}

.book-number {
    color: #8069b5;
    font-weight: 700;
    font-size: 0.9rem;
    margin-bottom: 8px;
}

.book-title {
    color: #3f3656;
    font-size: 1.3rem;
    font-weight: 800;
    margin-bottom: 18px;
}

.book-info {
    color: #555;
    font-size: 0.95rem;
    line-height: 2;
}

.call-number {
    background: #f4f0fb;
    color: #5d4c86;
    border-radius: 10px;
    padding: 10px 14px;
    margin-top: 15px;
    font-weight: 700;
}

/* 오늘의 책 */
.today-book {
    background: linear-gradient(135deg, #fffaf0, #fffdf8);
    border: 1px solid #f0dfb8;
    border-radius: 20px;
    padding: 25px;
    margin-top: 15px;
    margin-bottom: 18px;
    text-align: center;
}

.today-label {
    color: #b78628;
    font-size: 0.85rem;
    font-weight: 800;
    letter-spacing: 1px;
}

.today-title {
    color: #584a32;
    font-size: 1.25rem;
    font-weight: 800;
    margin-top: 8px;
}

/* 처음으로 */
.home-button > button {
    background: white !important;
    color: #6f5aa8 !important;
    border: 1px solid #d9d0eb !important;
    box-shadow: none !important;
}

.home-button > button:hover {
    background: #f7f3ff !important;
}

/* 푸터 */
.footer {
    text-align: center;
    color: #aaa;
    font-size: 0.8rem;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #eee;
}

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# 엑셀 데이터 불러오기
# --------------------------------------------------

file_path = "학습데이터.xlsx"


@st.cache_data
def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)


# --------------------------------------------------
# 값 정리 함수
# --------------------------------------------------

def clean_value(value):
    if value is None:
        return "정보 없음"

    try:
        if pd.isna(value):
            return "정보 없음"
    except:
        pass

    return str(value)


def get_book_info(row, position):
    try:
        return clean_value(row.iloc[position])
    except:
        return "정보 없음"


# --------------------------------------------------
# 전체 학습데이터에서 책 목록 만들기
# --------------------------------------------------

def make_all_books(all_topics_data):

    books = []

    for topic, df in all_topics_data.items():

        if df is None or df.empty:
            continue

        for _, row in df.iterrows():

            books.append({
                "topic": clean_value(topic),
                "reg_number": get_book_info(row, 0),
                "call_number": get_book_info(row, 1),
                "title": get_book_info(row, 2),
                "author": get_book_info(row, 3),
                "publisher": get_book_info(row, 4)
            })

    return books


# --------------------------------------------------
# 메인
# --------------------------------------------------

try:

    all_topics_data = load_data(file_path)

    # --------------------------------------------------
    # 이미지
    # --------------------------------------------------

    image_list = []

    if os.path.exists("aily1.png"):
        image_list.append("aily1.png")

    if os.path.exists("aily2.png"):
        image_list.append("aily2.png")

    if image_list:

        selected_image = random.choice(image_list)

        col1, col2, col3 = st.columns([1, 1.5, 1])

        with col2:
            st.image(
                selected_image,
                width="stretch"
            )

    # --------------------------------------------------
    # 제목
    # --------------------------------------------------

    st.markdown(
        '<div class="main-title">🐰 심곡도서관 보조사서 Aily</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">AI와 함께 발견하는 나만의 책</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------
    # 세션 상태
    # --------------------------------------------------

    if "mode" not in st.session_state:
        st.session_state["mode"] = "home"

    if "today_book" not in st.session_state:
        st.session_state["today_book"] = None

    if "recommended_books" not in st.session_state:
        st.session_state["recommended_books"] = None

    # --------------------------------------------------
    # HOME 화면
    # --------------------------------------------------

    if st.session_state["mode"] == "home":

        # 북큐레이션
        st.markdown("""
        <div class="menu-card">

            <div class="menu-title">
                📚 북큐레이션 추천
            </div>

            <div class="menu-description">
                관심 있는 주제를 선택하면<br>
                <b>Aily</b>가 책 3권을 추천해드려요.
            </div>

        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "📚 북큐레이션에서 3권 추천받기",
            key="curation_button"
        ):

            st.session_state["mode"] = "curation"
            st.session_state["recommended_books"] = None

            st.rerun()

        # 오늘의 한 권
        st.markdown("""
        <div class="menu-card">

            <div class="menu-title">
                🎁 오늘의 한 권
            </div>

            <div class="menu-description">
                학습데이터에 등록된 모든 도서 중<br>
                <b>Aily</b>가 오늘의 책 한 권을 골라드려요.
            </div>

        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "🎁 오늘의 한 권 만나보기",
            key="today_button"
        ):

            all_books = make_all_books(all_topics_data)

            if all_books:
                st.session_state["today_book"] = random.choice(all_books)
                st.session_state["mode"] = "today"

            else:
                st.warning("학습데이터에 등록된 도서가 없습니다.")

            st.rerun()

    # --------------------------------------------------
    # 북큐레이션 화면
    # --------------------------------------------------

    elif st.session_state["mode"] == "curation":

        st.markdown(
            '<div class="recommend-title">📚 북큐레이션 주제 선택</div>',
            unsafe_allow_html=True
        )

        topics = [
            topic
            for topic, df in all_topics_data.items()
            if df is not None and not df.empty
        ]

        if not topics:

            st.warning("학습데이터에 등록된 북큐레이션 주제가 없습니다.")

        else:

            selected_topic = st.selectbox(
                "어떤 주제의 책을 찾으시나요?",
                topics,
                key="topic_select"
            )

            selected_df = all_topics_data[selected_topic]

            st.caption(
                f"📖 '{selected_topic}' 주제 도서 "
                f"{len(selected_df):,}권"
            )

            if st.button(
                f"✨ '{selected_topic}' 책 3권 추천받기",
                key="recommend_button"
            ):

                num_books = min(3, len(selected_df))

                st.session_state["recommended_books"] = (
                    selected_df.sample(n=num_books)
                )

            # 추천 결과
            recommended = st.session_state["recommended_books"]

            if recommended is not None:

                st.markdown(
                    f'<div class="recommend-title">✨ Aily가 추천하는 {selected_topic} 도서</div>',
                    unsafe_allow_html=True
                )

                for book_index, (_, row) in enumerate(
                    recommended.iterrows(),
                    start=1
                ):

                    reg_number = get_book_info(row, 0)
                    call_number = get_book_info(row, 1)
                    title = get_book_info(row, 2)
                    author = get_book_info(row, 3)
                    publisher = get_book_info(row, 4)

                    st.markdown(
                        f"""
                        <div class="book-card">

                            <div class="book-number">
                                📚 Aily's PICK {book_index}
                            </div>

                            <div class="book-title">
                                📖 {title}
                            </div>

                            <div class="book-info">

                                👤 <b>저자</b>　{author}<br>

                                🏢 <b>출판사</b>　{publisher}<br>

                                🏷️ <b>등록번호</b>　{reg_number}

                            </div>

                            <div class="call-number">
                                📍 청구기호　{call_number}
                            </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        st.write("")

        # 처음으로
        st.markdown(
            '<div class="home-button">',
            unsafe_allow_html=True
        )

        if st.button(
            "🏠 처음으로 돌아가기",
            key="home_from_curation"
        ):

            st.session_state["mode"] = "home"
            st.session_state["recommended_books"] = None

            st.rerun()

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    # --------------------------------------------------
    # 오늘의 한 권 화면
    # --------------------------------------------------

    elif st.session_state["mode"] == "today":

        today_book = st.session_state["today_book"]

        if today_book is None:

            st.session_state["mode"] = "home"
            st.rerun()

        else:

            st.markdown("""
            <div class="today-book">

                <div class="today-label">
                    🎁 TODAY'S BOOK
                </div>

                <div class="today-title">
                    오늘 Aily가 선택한 한 권
                </div>

            </div>
            """, unsafe_allow_html=True)

            title = clean_value(today_book["title"])
            author = clean_value(today_book["author"])
            publisher = clean_value(today_book["publisher"])
            reg_number = clean_value(today_book["reg_number"])
            call_number = clean_value(today_book["call_number"])
            topic = clean_value(today_book["topic"])

            st.markdown(
                f"""
                <div class="book-card">

                    <div class="book-number">
                        🎁 Aily's PICK
                    </div>

                    <div class="book-title">
                        📖 {title}
                    </div>

                    <div class="book-info">

                        👤 <b>저자</b>　{author}<br>

                        🏢 <b>출판사</b>　{publisher}<br>

                        🏷️ <b>큐레이션 주제</b>　{topic}<br>

                        🎟️ <b>등록번호</b>　{reg_number}

                    </div>

                    <div class="call-number">
                        📍 청구기호　{call_number}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

            st.info(
                "💡 마음에 드는 책이라면 청구기호를 확인하고 "
                "도서관에서 찾아보세요!"
            )

            # 다른 책 뽑기
            if st.button(
                "🔄 다른 오늘의 책 뽑기",
                key="another_today"
            ):

                all_books = make_all_books(all_topics_data)

                if all_books:
                    st.session_state["today_book"] = random.choice(all_books)

                st.rerun()

        st.write("")

        # 처음으로
        st.markdown(
            '<div class="home-button">',
            unsafe_allow_html=True
        )

        if st.button(
            "🏠 처음으로 돌아가기",
            key="home_from_today"
        ):

            st.session_state["mode"] = "home"
            st.session_state["today_book"] = None

            st.rerun()

        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )

    # --------------------------------------------------
    # 푸터
    # --------------------------------------------------

    st.markdown("""
    <div class="footer">
        심곡도서관 × Aily &nbsp; | &nbsp; AI 북큐레이션
    </div>
    """, unsafe_allow_html=True)


# --------------------------------------------------
# 파일 오류
# --------------------------------------------------

except FileNotFoundError:

    st.error(
        "📂 엑셀 파일을 찾을 수 없습니다. "
        "'학습데이터.xlsx' 파일이 앱과 같은 폴더에 있는지 확인해주세요."
    )

except Exception as e:

    st.error("⚠️ 앱 실행 중 오류가 발생했습니다.")
    st.code(str(e))

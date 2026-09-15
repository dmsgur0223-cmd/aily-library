import streamlit as st
import pandas as pd
import random

# =========================================================
# 1. 웹 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="Aily 도서 추천",
    page_icon="🐰",
    layout="centered"
)

# =========================================================
# 2. 디자인
# =========================================================
st.markdown("""
<style>

.stApp {
    background: linear-gradient(
        180deg,
        #f8f6ff 0%,
        #ffffff 50%,
        #faf9ff 100%
    );
}

.block-container {
    max-width: 850px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

/* 메인 제목 */
.main-title {
    text-align: center;
    font-size: 2.1rem;
    font-weight: 800;
    color: #4b3f72;
    margin-top: 0.5rem;
    margin-bottom: 0.3rem;
}

.sub-title {
    text-align: center;
    color: #77718b;
    font-size: 1rem;
    margin-bottom: 2rem;
}

/* 메뉴 카드 */
.menu-card {
    background: white;
    border: 1px solid #ebe7f5;
    border-radius: 20px;
    padding: 22px;
    margin: 12px 0;
    box-shadow: 0 5px 20px rgba(90, 70, 130, 0.06);
}

.menu-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: #51456f;
    margin-bottom: 5px;
}

.menu-description {
    font-size: 0.9rem;
    color: #888;
    margin-bottom: 12px;
}

/* 버튼 */
.stButton > button {
    width: 100%;
    height: 52px;
    border-radius: 14px;
    border: none;
    background: linear-gradient(135deg, #6f5aa8, #8975c2);
    color: white;
    font-size: 1rem;
    font-weight: 700;
    box-shadow: 0 5px 15px rgba(111, 90, 168, 0.18);
    transition: 0.2s;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(111, 90, 168, 0.25);
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

/* 추천 결과 제목 */
.recommend-title {
    background: linear-gradient(135deg, #6f5aa8, #8b78c6);
    color: white;
    border-radius: 16px;
    padding: 15px 20px;
    margin: 25px 0 15px 0;
    font-size: 1.1rem;
    font-weight: 700;
}

/* 오늘의 한 권 */
.today-book {
    background: linear-gradient(
        135deg,
        #fffaf0,
        #ffffff
    );
    border: 1px solid #f0e4c7;
    border-radius: 20px;
    padding: 25px;
    margin-top: 20px;
    box-shadow: 0 6px 20px rgba(120, 90, 40, 0.08);
}

.today-label {
    color: #9a7835;
    font-size: 0.85rem;
    font-weight: 800;
    margin-bottom: 8px;
}

.today-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: #403827;
    margin-bottom: 15px;
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
# 3. 데이터 불러오기
# =========================================================
def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)


file_path = "학습데이터.xlsx"


try:

    all_topics_data = load_data(file_path)

    # =====================================================
    # 4. Aily 이미지
    # =====================================================
    image_list = ["aily1.png", "aily2.png"]
    selected_image = random.choice(image_list)

    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        try:
            st.image(
                selected_image,
                use_container_width=True
            )
        except FileNotFoundError:
            st.warning(
                "'aily1.png', 'aily2.png' 파일을 확인해주세요."
            )

    # =====================================================
    # 5. 제목
    # =====================================================
    st.markdown(
        '<div class="main-title">🐰 심곡도서관 보조사서 Aily</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="sub-title">AI와 함께 발견하는 나만의 책</div>',
        unsafe_allow_html=True
    )

    st.divider()


    # =====================================================
    # 6. 첫 화면 - 북큐레이션
    # =====================================================
    st.markdown(
        """
        <div class="menu-card">
            <div class="menu-title">
                📚 북큐레이션 추천
            </div>

            <div class="menu-description">
                관심 있는 주제를 선택하면
                Aily가 책 3권을 추천해드려요.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        "📚 북큐레이션에서 3권 추천받기",
        key="curation_button"
    ):
        st.session_state["mode"] = "curation"


    # =====================================================
    # 7. 첫 화면 - 오늘의 한 권
    # =====================================================
    st.markdown(
        """
        <div class="menu-card">
            <div class="menu-title">
                🎁 오늘의 한 권
            </div>

            <div class="menu-description">
                학습데이터에 등록된 모든 도서 중
                Aily가 오늘의 책 한 권을 골라드려요.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        "🎁 오늘의 한 권 만나보기",
        key="today_button"
    ):
        st.session_state["mode"] = "today"


    # =====================================================
    # 8. 북큐레이션 추천 화면
    # =====================================================
    if st.session_state.get("mode") == "curation":

        st.divider()

        st.markdown(
            """
            <div class="recommend-title">
                📚 북큐레이션 주제 선택
            </div>
            """,
            unsafe_allow_html=True
        )

        topics = list(all_topics_data.keys())

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

            df = all_topics_data[selected_topic]

            if df.empty:

                st.warning(
                    f"앗! '{selected_topic}' 주제에 "
                    "추천할 도서가 아직 비어있어요. 😅"
                )

            else:

                num_books = min(3, len(df))
                recommended = df.sample(n=num_books)

                st.markdown(
                    f"""
                    <div class="recommend-title">
                        🐰 Aily의 '{selected_topic}' 추천 도서
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                for book_index, (_, row) in enumerate(
                    recommended.iterrows(),
                    start=1
                ):

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


    # =====================================================
    # 9. 오늘의 한 권
    # =====================================================
    elif st.session_state.get("mode") == "today":

        st.divider()

        # 모든 시트의 도서를 하나로 합치기
        all_books = []

        for topic, df in all_topics_data.items():

            if not df.empty:

                for _, row in df.iterrows():

                    all_books.append({
                        "topic": topic,

                        "reg_number":
                            row.iloc[0]
                            if len(row) > 0
                            else "정보 없음",

                        "call_number":
                            row.iloc[1]
                            if len(row) > 1
                            else "정보 없음",

                        "title":
                            row.iloc[2]
                            if len(row) > 2
                            else "정보 없음",

                        "author":
                            row.iloc[3]
                            if len(row) > 3
                            else "정보 없음",

                        "publisher":
                            row.iloc[4]
                            if len(row) > 4
                            else "정보 없음"
                    })


        if not all_books:

            st.warning(
                "학습데이터에 등록된 도서가 없습니다."
            )

        else:

            today_book = random.choice(all_books)


            # -------------------------------------------------
            # 값 정리
            # -------------------------------------------------
            def clean_value(value):

                if pd.isna(value):
                    return "정보 없음"

                return str(value)


            title = clean_value(today_book["title"])
            author = clean_value(today_book["author"])
            publisher = clean_value(today_book["publisher"])
            reg_number = clean_value(today_book["reg_number"])
            call_number = clean_value(today_book["call_number"])
            topic = clean_value(today_book["topic"])


            # -------------------------------------------------
            # 오늘의 책 제목
            # -------------------------------------------------
            st.markdown(
                """
                <div class="today-book">

                    <div class="today-label">
                        🎁 TODAY'S BOOK
                    </div>

                    <div class="today-title">
                        오늘 Aily가 선택한 한 권
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


            # -------------------------------------------------
            # 책 정보
            # -------------------------------------------------
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

                        🔖 <b>등록번호</b>　{reg_number}<br>

                        <div class="call-number">
                            📍 청구기호　{call_number}
                        </div>

                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


            st.info(
                "💡 마음에 드는 책이라면 청구기호를 확인하고 "
                "도서관에서 찾아보세요!"
            )


    # =====================================================
    # 10. 하단
    # =====================================================
    st.markdown(
        """
        <div class="footer">
            심곡도서관 × Aily &nbsp; | &nbsp; AI 북큐레이션
        </div>
        """,
        unsafe_allow_html=True
    )


except FileNotFoundError:

    st.error(
        "📂 엑셀 파일을 찾을 수 없습니다. "
        "'학습데이터.xlsx' 파일이 앱과 같은 폴더에 있는지 확인해주세요."
    )

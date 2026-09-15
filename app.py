import streamlit as st
import pandas as pd
import random

# 1. 웹 페이지 기본 설정
st.set_page_config(
    page_title="Aily 도서 추천",
    page_icon="🐰"
)

# --------------------------------------------------
# 이미지
# --------------------------------------------------

image_list = ["aily1.png", "aily2.png"]
selected_image = random.choice(image_list)

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    try:
        st.image(selected_image, use_container_width=True)
    except FileNotFoundError:
        st.warning(
            "이미지 파일을 찾을 수 없습니다. "
            "'aily1.png', 'aily2.png' 파일이 있는지 확인해주세요!"
        )


# --------------------------------------------------
# 제목
# --------------------------------------------------

st.title("🐰 심곡도서관 보조사서 Aily")
st.subheader("북큐레이션 주제 탐색!")

st.caption("※ 이미 대출중일수도 있어요! 😅")

st.divider()


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)


file_path = "학습데이터.xlsx"


# --------------------------------------------------
# 메인
# --------------------------------------------------

try:

    all_topics_data = load_data(file_path)
    topics = list(all_topics_data.keys())

    # --------------------------------------------------
    # 기능 선택
    # --------------------------------------------------

    menu = st.radio(
        "Aily 메뉴",
        ["📚 북큐레이션 추천", "🔎 중복자료 점검"],
        horizontal=True
    )

    st.divider()


    # ==================================================
    # 1. 북큐레이션 추천
    # ==================================================

    if menu == "📚 북큐레이션 추천":

        selected_topic = st.selectbox(
            "어떤 주제의 책을 찾으시나요?",
            topics
        )

        if st.button(
            f"'{selected_topic}' 책 추천받기 🎁"
        ):

            df = all_topics_data[selected_topic]

            if df.empty:

                st.warning(
                    f"앗! '{selected_topic}' 주제에 추천할 "
                    "도서가 아직 비어있습니다. 😅"
                )

            else:

                num_books = min(3, len(df))
                recommended = df.sample(n=num_books)

                st.success("AILY의 추천 ❤️")

                for index, row in recommended.iterrows():

                    try:
                        reg_number = row.iloc[0]
                        call_number = row.iloc[1]
                        title = row.iloc[2]
                        author = row.iloc[3]
                        publisher = row.iloc[4]

                    except IndexError:

                        reg_number = "정보 없음"
                        call_number = "정보 없음"
                        title = "정보 없음"
                        author = "정보 없음"
                        publisher = "정보 없음"

                    st.info(
                        f"📖 **{title}**\n\n"
                        f"👤 저자/발행: {author} / {publisher}\n\n"
                        f"📍 청구기호: **{call_number}**\n\n"
                        f"🔖 등록번호: {reg_number}"
                    )


    # ==================================================
    # 2. 중복자료 점검
    # ==================================================

    elif menu == "🔎 중복자료 점검":

        st.subheader("🔎 도서목록 중복자료 점검")

        st.caption(
            "지난 북큐레이션 목록을 확인하여 "
            "등록번호 및 제목·저자 기준의 중복자료를 찾아냅니다."
        )

        if st.button("🔍 중복자료 검사 시작"):

            # ------------------------------------------
            # 전체 데이터를 하나로 합치기
            # ------------------------------------------

            all_books = []

            for topic, df in all_topics_data.items():

                if df.empty:
                    continue

                for row_index, row in df.iterrows():

                    try:
                        reg_number = row.iloc[0]
                    except IndexError:
                        reg_number = ""

                    try:
                        call_number = row.iloc[1]
                    except IndexError:
                        call_number = ""

                    try:
                        title = row.iloc[2]
                    except IndexError:
                        title = ""

                    try:
                        author = row.iloc[3]
                    except IndexError:
                        author = ""

                    try:
                        publisher = row.iloc[4]
                    except IndexError:
                        publisher = ""

                    # 빈값 정리
                    reg_number = "" if pd.isna(reg_number) else str(reg_number).strip()
                    call_number = "" if pd.isna(call_number) else str(call_number).strip()
                    title = "" if pd.isna(title) else str(title).strip()
                    author = "" if pd.isna(author) else str(author).strip()
                    publisher = "" if pd.isna(publisher) else str(publisher).strip()

                    all_books.append({
                        "시트": topic,
                        "행": row_index + 2,
                        "등록번호": reg_number,
                        "청구기호": call_number,
                        "제목": title,
                        "저자": author,
                        "출판사": publisher
                    })


            # ------------------------------------------
            # 데이터가 없는 경우
            # ------------------------------------------

            if not all_books:

                st.warning("학습데이터에 등록된 도서가 없습니다.")

            else:

                books_df = pd.DataFrame(all_books)

                # ======================================
                # 검사 1. 등록번호 중복
                # ======================================

                reg_df = books_df[
                    books_df["등록번호"] != ""
                ].copy()

                duplicate_reg = reg_df[
                    reg_df.duplicated(
                        subset=["등록번호"],
                        keep=False
                    )
                ].sort_values("등록번호")


                # ======================================
                # 검사 2. 제목 + 저자 중복
                # ======================================

                title_author_df = books_df[
                    (books_df["제목"] != "") &
                    (books_df["저자"] != "")
                ].copy()

                duplicate_title_author = title_author_df[
                    title_author_df.duplicated(
                        subset=["제목", "저자"],
                        keep=False
                    )
                ].sort_values(["제목", "저자"])


                # ======================================
                # 검사 결과 요약
                # ======================================

                st.divider()

                total_books = len(books_df)
                reg_count = len(duplicate_reg)
                title_author_count = len(duplicate_title_author)

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "전체 자료",
                        f"{total_books:,}권"
                    )

                with col2:
                    st.metric(
                        "등록번호 중복",
                        f"{reg_count:,}건"
                    )

                with col3:
                    st.metric(
                        "제목·저자 중복",
                        f"{title_author_count:,}건"
                    )


                # ======================================
                # 등록번호 중복 결과
                # ======================================

                st.markdown("### 🔴 등록번호 중복자료")

                if duplicate_reg.empty:

                    st.success(
                        "등록번호가 중복된 자료가 없습니다. 👍"
                    )

                else:

                    st.warning(
                        f"등록번호가 중복된 자료가 "
                        f"{len(duplicate_reg)}건 발견되었습니다."
                    )

                    display_reg = duplicate_reg[
                        [
                            "시트",
                            "행",
                            "등록번호",
                            "제목",
                            "저자",
                            "청구기호"
                        ]
                    ]

                    st.dataframe(
                        display_reg,
                        use_container_width=True,
                        hide_index=True
                    )


                # ======================================
                # 제목 + 저자 중복 결과
                # ======================================

                st.markdown("### 🟠 제목·저자 중복자료")

                if duplicate_title_author.empty:

                    st.success(
                        "제목과 저자가 동일한 자료가 없습니다. 👍"
                    )

                else:

                    st.warning(
                        f"제목과 저자가 동일한 자료가 "
                        f"{len(duplicate_title_author)}건 발견되었습니다."
                    )

                    display_title = duplicate_title_author[
                        [
                            "시트",
                            "행",
                            "제목",
                            "저자",
                            "출판사",
                            "등록번호",
                            "청구기호"
                        ]
                    ]

                    st.dataframe(
                        display_title,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.caption(
                        "※ 제목·저자가 같은 자료는 실제로 동일 도서일 수도 있고, "
                        "판본·번역본·개정판 등이 다를 수도 있으므로 "
                        "최종 확인이 필요합니다."
                    )


                # ======================================
                # 시트 간 중복 확인
                # ======================================

                st.markdown("### 🟡 여러 북큐레이션에 등록된 자료")

                if not duplicate_title_author.empty:

                    # 같은 제목+저자가 몇 개의 시트에 들어있는지 확인
                    sheet_duplicate = (
                        duplicate_title_author
                        .groupby(["제목", "저자"])["시트"]
                        .nunique()
                        .reset_index(name="등록된_주제_수")
                    )

                    sheet_duplicate = sheet_duplicate[
                        sheet_duplicate["등록된_주제_수"] > 1
                    ]

                    if sheet_duplicate.empty:

                        st.info(
                            "서로 다른 북큐레이션 주제에 "
                            "동일한 제목·저자의 책이 등록된 자료는 없습니다."
                        )

                    else:

                        st.warning(
                            f"여러 북큐레이션 주제에 중복 등록된 "
                            f"도서가 {len(sheet_duplicate)}종 있습니다."
                        )

                        result_list = []

                        for _, item in sheet_duplicate.iterrows():

                            title = item["제목"]
                            author = item["저자"]

                            matching = duplicate_title_author[
                                (duplicate_title_author["제목"] == title) &
                                (duplicate_title_author["저자"] == author)
                            ]

                            topics_text = ", ".join(
                                matching["시트"].astype(str).unique()
                            )

                            result_list.append({
                                "제목": title,
                                "저자": author,
                                "등록된 주제": topics_text
                            })

                        st.dataframe(
                            pd.DataFrame(result_list),
                            use_container_width=True,
                            hide_index=True
                        )

                else:

                    st.info(
                        "확인할 중복자료가 없습니다."
                    )


                # ======================================
                # 검사 완료
                # ======================================

                if (
                    duplicate_reg.empty
                    and duplicate_title_author.empty
                ):

                    st.success(
                        "🎉 중복자료 점검 완료! "
                        "현재 학습데이터에서 중복자료가 발견되지 않았습니다."
                    )

                else:

                    st.info(
                        "💡 중복으로 표시된 자료를 실제 도서관 자료와 "
                        "대조하여 최종적으로 확인해주세요."
                    )


except FileNotFoundError:

    st.error(
        "엑셀 파일을 찾을 수 없습니다. "
        "'학습데이터.xlsx' 파일이 앱과 같은 폴더에 있는지 확인해주세요."
    )

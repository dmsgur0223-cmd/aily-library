import streamlit as st
import pandas as pd
import random
import io

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

st.divider()


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)


file_path = "학습데이터.xlsx"


# --------------------------------------------------
# 데이터 값 정리
# --------------------------------------------------

def clean_value(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize(value):
    """
    비교할 때 불필요한 앞뒤 공백을 제거하고
    여러 개의 공백을 하나로 통일합니다.
    """
    if pd.isna(value):
        return ""

    value = str(value).strip().lower()
    value = " ".join(value.split())

    return value


def get_book_info(row, position):
    try:
        return clean_value(row.iloc[position])
    except IndexError:
        return ""


# --------------------------------------------------
# 메인
# --------------------------------------------------

try:

    # 기존 학습데이터
    all_topics_data = load_data(file_path)

    topics = list(all_topics_data.keys())


    # --------------------------------------------------
    # 메뉴
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

        st.subheader("🔎 중복자료 점검")

        st.caption(
            "새로운 엑셀 파일을 업로드하면 "
            "현재 학습데이터.xlsx와 비교하여 "
            "중복자료 여부를 확인합니다."
        )


        # --------------------------------------------------
        # 학습데이터 전체를 하나로 합치기
        # --------------------------------------------------

        learning_books = []

        for topic, df in all_topics_data.items():

            if df is None or df.empty:
                continue

            for row_index, row in df.iterrows():

                reg_number = get_book_info(row, 0)
                call_number = get_book_info(row, 1)
                title = get_book_info(row, 2)
                author = get_book_info(row, 3)
                publisher = get_book_info(row, 4)

                learning_books.append({
                    "학습데이터_주제": topic,
                    "학습데이터_행": row_index + 2,
                    "등록번호": reg_number,
                    "청구기호": call_number,
                    "제목": title,
                    "저자": author,
                    "출판사": publisher
                })


        learning_df = pd.DataFrame(learning_books)


        # --------------------------------------------------
        # 엑셀 업로드
        # --------------------------------------------------

        st.markdown("### 📂 비교할 엑셀 파일 업로드")

        uploaded_file = st.file_uploader(
            "학습데이터와 비교할 Excel 파일을 넣어주세요.",
            type=["xlsx"],
            help="엑셀 파일의 도서 정보는 기존 학습데이터와 동일하게 등록번호, 청구기호, 제목, 저자, 출판사 순서를 권장합니다."
        )


        if uploaded_file is not None:

            try:

                # --------------------------------------------------
                # 업로드한 엑셀 읽기
                # --------------------------------------------------

                uploaded_data = pd.read_excel(
                    uploaded_file,
                    sheet_name=None
                )

                uploaded_sheets = list(uploaded_data.keys())


                # --------------------------------------------------
                # 여러 시트가 있을 경우 선택
                # --------------------------------------------------

                if len(uploaded_sheets) > 1:

                    selected_upload_sheet = st.selectbox(
                        "비교할 시트를 선택해주세요.",
                        uploaded_sheets
                    )

                    upload_df = uploaded_data[
                        selected_upload_sheet
                    ]

                else:

                    selected_upload_sheet = uploaded_sheets[0]

                    upload_df = uploaded_data[
                        selected_upload_sheet
                    ]


                st.success(
                    f"📄 '{selected_upload_sheet}' 시트를 불러왔습니다."
                )


                if upload_df.empty:

                    st.warning(
                        "업로드한 엑셀 시트에 도서자료가 없습니다."
                    )


                else:

                    # --------------------------------------------------
                    # 학습데이터 비교용 목록 만들기
                    # --------------------------------------------------

                    learning_reg_numbers = set()
                    learning_title_author = {}

                    for _, book in learning_df.iterrows():

                        reg = normalize(book["등록번호"])
                        title = normalize(book["제목"])
                        author = normalize(book["저자"])

                        if reg:
                            learning_reg_numbers.add(reg)

                        if title and author:

                            key = (
                                title,
                                author
                            )

                            if key not in learning_title_author:
                                learning_title_author[key] = []

                            learning_title_author[key].append(
                                book
                            )


                    # --------------------------------------------------
                    # 업로드 자료 하나씩 비교
                    # --------------------------------------------------

                    comparison_results = []


                    for row_index, row in upload_df.iterrows():

                        reg_number = get_book_info(row, 0)
                        call_number = get_book_info(row, 1)
                        title = get_book_info(row, 2)
                        author = get_book_info(row, 3)
                        publisher = get_book_info(row, 4)


                        normalized_reg = normalize(
                            reg_number
                        )

                        normalized_title = normalize(
                            title
                        )

                        normalized_author = normalize(
                            author
                        )


                        # ------------------------------------------
                        # 중복 여부 판단
                        # ------------------------------------------

                        duplicate_reason = []
                        matched_books = []


                        # ① 등록번호 비교

                        if (
                            normalized_reg
                            and normalized_reg in learning_reg_numbers
                        ):

                            duplicate_reason.append(
                                "등록번호 동일"
                            )


                            matched_reg = learning_df[
                                learning_df["등록번호"].apply(
                                    normalize
                                ) == normalized_reg
                            ]

                            matched_books.extend(
                                matched_reg.to_dict("records")
                            )


                        # ② 제목 + 저자 비교

                        title_author_key = (
                            normalized_title,
                            normalized_author
                        )


                        if (
                            normalized_title
                            and normalized_author
                            and title_author_key in learning_title_author
                        ):

                            duplicate_reason.append(
                                "제목+저자 동일"
                            )

                            matched_books.extend(
                                learning_title_author[
                                    title_author_key
                                ]
                            )


                        # 중복자료
                        if duplicate_reason:

                            status = "🔴 중복"

                            reason = " / ".join(
                                duplicate_reason
                            )

                        # 신규자료
                        else:

                            status = "🟢 신규"

                            reason = "학습데이터에 없음"


                        # ------------------------------------------
                        # 기존 학습데이터 정보
                        # ------------------------------------------

                        matched_title = ""
                        matched_author = ""
                        matched_topic = ""


                        if matched_books:

                            matched_book = matched_books[0]

                            matched_title = clean_value(
                                matched_book["제목"]
                            )

                            matched_author = clean_value(
                                matched_book["저자"]
                            )

                            matched_topic = clean_value(
                                matched_book["학습데이터_주제"]
                            )


                        comparison_results.append({

                            "판정": status,

                            "엑셀 행": row_index + 2,

                            "등록번호": reg_number,

                            "제목": title,

                            "저자": author,

                            "출판사": publisher,

                            "판정 사유": reason,

                            "학습데이터 내 기존 제목":
                                matched_title,

                            "학습데이터 내 기존 저자":
                                matched_author,

                            "기존 등록 주제":
                                matched_topic

                        })


                    # --------------------------------------------------
                    # 결과 데이터프레임
                    # --------------------------------------------------

                    result_df = pd.DataFrame(
                        comparison_results
                    )


                    # --------------------------------------------------
                    # 결과 요약
                    # --------------------------------------------------

                    total_count = len(result_df)

                    duplicate_count = len(
                        result_df[
                            result_df["판정"] == "🔴 중복"
                        ]
                    )

                    new_count = len(
                        result_df[
                            result_df["판정"] == "🟢 신규"
                        ]
                    )


                    st.divider()

                    st.markdown("### 📊 비교 결과")


                    col1, col2, col3 = st.columns(3)


                    with col1:

                        st.metric(
                            "업로드 자료",
                            f"{total_count:,}권"
                        )


                    with col2:

                        st.metric(
                            "🔴 중복",
                            f"{duplicate_count:,}권"
                        )


                    with col3:

                        st.metric(
                            "🟢 신규",
                            f"{new_count:,}권"
                        )


                    # --------------------------------------------------
                    # 전체 결과
                    # --------------------------------------------------

                    st.markdown("### 📋 전체 검사 결과")

                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True
                    )


                    # --------------------------------------------------
                    # 중복자료만 보기
                    # --------------------------------------------------

                    st.markdown("### 🔴 중복자료")

                    duplicate_result = result_df[
                        result_df["판정"] == "🔴 중복"
                    ]


                    if duplicate_result.empty:

                        st.success(
                            "🎉 학습데이터와 중복되는 자료가 없습니다!"
                        )

                    else:

                        st.warning(
                            f"총 {len(duplicate_result)}권의 "
                            "중복자료가 발견되었습니다."
                        )

                        st.dataframe(
                            duplicate_result,
                            use_container_width=True,
                            hide_index=True
                        )


                    # --------------------------------------------------
                    # 신규자료만 보기
                    # --------------------------------------------------

                    st.markdown("### 🟢 신규자료")

                    new_result = result_df[
                        result_df["판정"] == "🟢 신규"
                    ]


                    if new_result.empty:

                        st.info(
                            "새롭게 등록할 자료가 없습니다."
                        )

                    else:

                        st.success(
                            f"총 {len(new_result)}권이 "
                            "학습데이터에 없는 신규자료입니다."
                        )

                        st.dataframe(
                            new_result,
                            use_container_width=True,
                            hide_index=True
                        )


                    # --------------------------------------------------
                    # 결과 다운로드
                    # --------------------------------------------------

                    st.markdown("### 💾 검사 결과 저장")

                    output = io.BytesIO()

                    with pd.ExcelWriter(
                        output,
                        engine="openpyxl"
                    ) as writer:

                        result_df.to_excel(
                            writer,
                            index=False,
                            sheet_name="중복검사결과"
                        )

                        duplicate_result.to_excel(
                            writer,
                            index=False,
                            sheet_name="중복자료"
                        )

                        new_result.to_excel(
                            writer,
                            index=False,
                            sheet_name="신규자료"
                        )


                    st.download_button(
                        label="📥 검사 결과 엑셀로 저장",
                        data=output.getvalue(),
                        file_name="Aily_중복자료검사결과.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


                    # --------------------------------------------------
                    # 안내
                    # --------------------------------------------------

                    st.caption(
                        "※ 중복 판정은 등록번호 또는 제목+저자가 "
                        "학습데이터와 일치하는 경우입니다. "
                        "제목·저자가 동일하더라도 판본이나 개정판 등이 "
                        "다를 수 있으므로 최종 확인이 필요합니다."
                    )


            except Exception as e:

                st.error(
                    "업로드한 엑셀 파일을 읽는 중 오류가 발생했습니다."
                )

                st.code(str(e))


except FileNotFoundError:

    st.error(
        "학습데이터.xlsx 파일을 찾을 수 없습니다. "
        "학습데이터.xlsx가 app.py와 같은 폴더에 있는지 확인해주세요."
    )

import streamlit as st
import pandas as pd
import random

# 1. 웹 페이지 기본 설정 (탭 아이콘 변경)
st.set_page_config(page_title="심곡도서관 AILY", page_icon="🐰", layout="centered")

# CSS를 이용해 전체 배경색과 귀여운 손글씨 폰트를 지정합니다.
st.markdown("""
    <style>
    /* 폰트 불러오기 (나눔손글씨 붓) */
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Brush+Script&display=swap');

    /* 전체 배경색 및 폰트 설정 */
    .stApp {
        background-color: #FFFDF8; /* 부드러운 크림색 */
    }
    
    html, body, [class*="css"] {
        font-family: 'Nanum Brush Script', cursive !important; /* 귀여운 손글씨 */
        color: #555;
        font-size: 1.2em; /* 손글씨는 크게 봐야 귀여워요 */
    }
    
    /* 제목 스타일 커스텀 */
    h1 {
        color: #FFB6C1 !important; /* 파스텔 핑크 */
        font-weight: 800;
        text-align: center;
        font-size: 2.5em;
        margin-bottom: 30px;
    }
    
    /* 버튼 스타일 커스텀 */
    .stButton>button {
        background-color: #FFB6C1; /* 파스텔 핑크 */
        color: white;
        border-radius: 25px; /* 아주 둥글게 */
        border: none;
        padding: 10px 25px;
        font-size: 1.2em;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #FF99AA; /* 조금 더 진한 핑크 */
        transform: scale(1.1);
    }
    </style>
""", unsafe_allow_html=True)


# 데이터 로드 함수 (캐싱 적용)
@st.cache_data
def load_data(file_name):
    try:
        return pd.read_excel(file_name, sheet_name=None)
    except FileNotFoundError:
        return None

file_path = '학습데이터.xlsx'
all_topics_data = load_data(file_path)


# --- 사이드바 영역 (귀엽게 꾸미기) ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #FFB6C1; font-family: 'Nanum Brush Script', cursive;'>🐰 AILY 설정 🐰</h2>", unsafe_allow_html=True)
    image_list = ["aily1.png", "aily2.png"]
    try:
        # 이미지가 있다면 랜덤하게 표시
        st.image(random.choice(image_list), use_container_width=True)
    except:
        # 이미지가 없을 때를 대비한 예외 처리
        st.warning("이미지 파일을 찾을 수 없습니다. ('aily1.png', 'aily2.png' 확인)")
    
    st.divider()
    st.caption("🏢 심곡도서관 보조사서 AILY")
    st.caption("💬 무엇이든 물어보세요!")
    st.caption("⚠️ 이미 대출 중일 수도 있어요 😅")


# --- 메인 화면 영역 ---
st.title("🎀 심곡도서관 도서 처방전 🎀")

if all_topics_data:
    topics = list(all_topics_data.keys())
    
    # 주제 선택창 (디자인된 테마 적용됨)
    selected_topic = st.selectbox("어떤 주제의 책을 찾으시나요?", ["주제를 선택해 주세요"] + topics)
    
    # 추천받기 버튼
    if st.button(f"'{selected_topic}' 책 추천받기 🎁") and selected_topic != "주제를 선택해 주세요":
        with st.spinner('AILY가 서가에서 책을 찾는 중...'):
            df = all_topics_data[selected_topic]
            
            if df.empty:
                st.warning(f"앗! '{selected_topic}' 주제에 추천할 도서가 아직 비어있습니다. 😅")
            else:
                num_books = min(3, len(df))
                recommended = df.sample(n=num_books)
                
                # 결과 상단 메시지
                st.markdown(f"<h3 style='text-align: center; color: #FF99AA; margin-top: 30px;'>❤️ AILY의 맞춤 처방 ❤️</h3>", unsafe_allow_html=True)
                
                for _, row in recommended.iterrows():
                    try:
                        # 데이터 인덱싱 (기존 코드 유지)
                        reg_number, call_number, title, author, publisher = row.iloc[0], row.iloc[1], row.iloc[2], row.iloc[3], row.iloc[4]
                    except IndexError:
                        reg_number, call_number, title, author, publisher = "정보 없음", "정보 없음", "정보 없음", "정보 없음", "정보 없음"
                    
                    # --- [핵심] HTML/CSS 기반 귀여운 구름 카드 디자인 주입 ---
                    book_card_html = f"""
                    <div style="
                        background-color: #ffffff;
                        padding: 30px;
                        border-radius: 20px;
                        border-left: 10px solid #FFB6C1;
                        box-shadow: 2px 2px 20px rgba(0,0,0,0.1);
                        margin-bottom: 25px;
                        transition: transform 0.2s ease;
                    ">
                        <h2 style="color: #FFB6C1; margin-top: 0; margin-bottom: 10px; font-family: 'Nanum Brush Script', cursive !important;">📖 {title}</h2>
                        <p style="color: #777; font-size: 0.9em; margin-bottom: 15px;">👤 저자/발행: {author} / {publisher}</p>
                        
                        <div style="
                            background-color: #FFF0F5; /* 파스텔 핑크 */
                            padding: 15px;
                            border-radius: 15px;
                            border: 2px dashed #EAE0D5;
                        ">
                            <p style="margin: 0; font-weight: bold; color: #FFB6C1; font-size: 1.2em; font-family: 'Nanum Brush Script', cursive !important;">📍 청구기호: {call_number}</p>
                            <p style="margin: 5px 0 0 0; font-size: 0.9em; color: #999; font-family: 'Nanum Brush Script', cursive !important;">🔖 등록번호: {reg_number}</p>
                        </div>
                        
                        <p style="margin-top: 15px; margin-bottom: 0; color: #6F5642; font-style: italic; font-family: 'Nanum Brush Script', cursive !important;">
                            👩‍🏫 사서 AILY의 한마디: "이 책은 {selected_topic} 주제를 처음 접하는 분들에게 딱 맞는 깊이와 재미를 가지고 있어요. 꼭 한 번 읽어보시길 권해드려요!"
                        </p>
                    </div>
                    """
                    # st.markdown을 이용해 HTML 코드를 화면에 그립니다.
                    st.markdown(book_card_html, unsafe_allow_html=True)
                    
                # 하단 안내 멘트
                st.caption("※ 도서관 홈페이지에서 실시간 대출 상태를 꼭 확인해 주세요!")

else:
    st.error("엑셀 파일을 찾을 수 없습니다. '학습데이터.xlsx' 파일이 있는지 확인해주세요.")

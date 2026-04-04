import streamlit as st
import pandas as pd
import random
import base64

# 1. 페이지 설정
st.set_page_config(page_title="심곡도서관 AILY의 책장", page_icon="🐰", layout="centered")

# --- 기깔나는 디자인 주입 (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Brush+Script&display=swap');

    /* 1. 배경: 포근한 모눈종이 느낌 */
    .stApp {
        background-color: #fdfbf7;
        background-image:  radial-gradient(#e5e5f7 0.5px, transparent 0.5px), radial-gradient(#e5e5f7 0.5px, #fdfbf7 0.5px);
        background-size: 20px 20px;
        background-position: 0 0,10px 10px;
    }

    /* 2. 폰트 및 텍스트 스타일 */
    html, body, [class*="css"] {
        font-family: 'Nanum Brush Script', cursive !important;
        font-size: 1.4em;
        color: #5d4037;
    }

    /* 3. 아일리의 책장 카드 (대출증 느낌) */
    .book-card {
        background: #ffffff;
        border-radius: 15px;
        padding: 25px;
        margin-bottom: 25px;
        border: 2px solid #ffb6c1;
        box-shadow: 8px 8px 0px #ffb6c1; /* 입체적인 테두리 그림자 */
        position: relative;
        overflow: hidden;
    }
    
    .book-card::after {
        content: "LIBRARY CHECKOUT";
        position: absolute;
        top: 10px;
        right: -30px;
        background: #ffb6c1;
        color: white;
        padding: 5px 40px;
        transform: rotate(45deg);
        font-size: 0.6em;
        font-weight: bold;
    }

    /* 4. 버튼 디자인 */
    .stButton>button {
        background-color: #ffb6c1;
        color: white;
        border-radius: 50px;
        border: none;
        padding: 10px 30px;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(255, 182, 193, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# 2. 데이터 로드
@st.cache_data
def load_data(file_name):
    try:
        return pd.read_excel(file_name, sheet_name=None)
    except: return None

all_topics_data = load_data('학습데이터.xlsx')

# --- 상단 영역 (아일리의 인사) ---
col1, col2 = st.columns([1, 4])
with col1:
    try: st.image("aily1.png", width=100)
    except: pass
with col2:
    st.markdown("<h1 style='margin-top: 10px; color: #ff8fa3;'>📚 아일리의 책장에 오신 걸 환영해요!</h1>", unsafe_allow_html=True)

st.write("안녕! 나는 심곡도서관 신입 사원 아일리야. 오늘은 어떤 테마로 책장을 채워볼까?")

# --- 북큐레이션 영역 ---
if all_topics_data:
    topics = list(all_topics_data.keys())
    selected_topic = st.selectbox("아일리에게 주제를 알려줘! 🐰", ["선택해 주세요"] + topics)

    if st.button("아일리, 책 골라줘! ✨") and selected_topic != "선택해 주세요":
        with st.spinner('아일리가 사다리를 타고 책을 꺼내오는 중...'):
            df = all_topics_data[selected_topic]
            recommended = df.sample(n=min(3, len(df)))
            
            st.markdown(f"### 🎀 '{selected_topic}' 테마의 추천 도서들")
            
            for _, row in recommended.iterrows():
                # 데이터 매칭 (원본 로직 유지)
                reg_num, call_num, title, author, pub = row.iloc[0], row.iloc[1], row.iloc[2], row.iloc[3], row.iloc[4]
                
                st.markdown(f"""
                    <div class="book-card">
                        <h2 style="color: #ff8fa3; margin-bottom: 5px;">📖 {title}</h2>
                        <p style="font-size: 0.9em; margin-bottom: 15px;">저자/발행: {author} / {pub}</p>
                        <div style="background: #fff5f7; padding: 10px; border-radius: 10px; display: inline-block; width: 100%;">
                            <span style="color: #ff8fa3; font-weight: bold;">📍 청구기호: {call_num}</span><br>
                            <span style="font-size: 0.8em; color: #999;">🔖 등록번호: {reg_num}</span>
                        </div>
                        <p style="margin-top: 15px; font-size: 0.95em; color: #8e6e53;">
                            💬 아일리의 한마디: "{selected_topic}에 관심이 있다면 이 책이 딱이야! 내가 우리 도서관 서가에서 어렵게 찾아냈어. 꼭 읽어봐!"
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            
            st.balloons()
            st.caption("※ 이미 대출 중일 수도 있으니 홈페이지 확인 잊지 마! 😅")
else:
    st.error("데이터 파일을 찾을 수 없어. 깃허브에 '학습데이터.xlsx'가 있는지 확인해줘!")

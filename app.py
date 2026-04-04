import streamlit as st
import pandas as pd
import random
import base64

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="심곡도서관 AILY", page_icon="🐰", layout="centered")

# --- [추가] 로컬 이미지를 배경으로 쓰기 위한 함수 ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# 배경으로 쓸 이미지를 하나 선택하세요 (예: aily1.png가 배경으로 적당하다면)
try:
    bin_str = get_base64_of_bin_file('aily3.png') # 배경 이미지 파일명
    bg_img_style = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{bin_str}");
        background-size: cover;
        background-attachment: fixed;
        background-opacity: 0.1; /* 배경 투명도 조절이 직접 안되므로 아래 overlay 참고 */
    }}
    /* 배경 위에 반투명 덮개(Overlay)를 씌워 글씨 가독성을 높입니다 */
    .stApp::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        background-color: rgba(255, 253, 248, 0.85); /* 크림색 85% 불투명도 */
        z-index: -1;
    }}
    </style>
    """
    st.markdown(bg_img_style, unsafe_allow_html=True)
except:
    # 이미지 파일이 없을 경우 따뜻한 그라데이션 배경으로 대체
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #FFF5F7 0%, #FFFDF8 100%);
        }
        </style>
    """, unsafe_allow_html=True)

# --- 기존 CSS 유지 및 보강 ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Brush+Script&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Nanum Brush Script', cursive !important;
        color: #555;
        font-size: 1.35em;
    }
    
    h1, h2, h3 { color: #FFB6C1 !important; text-align: center; }

    /* 메인 콘텐츠 영역을 하얀색 둥근 박스로 감싸서 휑한 느낌 없애기 */
    .main-container {
        background-color: rgba(255, 255, 255, 0.9);
        padding: 30px;
        border-radius: 30px;
        box-shadow: 0 10px 25px rgba(255, 182, 193, 0.2);
    }
    
    .info-card {
        background-color: white; 
        padding: 20px; 
        border-radius: 20px; 
        border: 2.5px dashed #FFB6C1;
        box-shadow: 2px 5px 15px rgba(0,0,0,0.03);
        margin-bottom: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# 데이터 로드 함수
@st.cache_data
def load_data(file_name):
    try:
        return pd.read_excel(file_name, sheet_name=None)
    except: return None

all_topics_data = load_data('학습데이터.xlsx')

# --- 사이드바 메뉴 ---
with st.sidebar:
    st.markdown("<h1 style='font-size: 2.2em;'>🐰 AILY와 함께</h1>", unsafe_allow_html=True)
    menu = st.radio("어디로 갈까요?", ["✨ 북큐레이션 추천", "🎀 Aily에 대해", "📚 주제별 책 추천"])
    st.divider()
    try:
        st.image(random.choice(["aily1.png", "aily2.png"]), use_container_width=True)
    except: pass

# --- 메인 화면 컨테이너 시작 ---
st.markdown('<div class="main-container">', unsafe_allow_html=True)

if menu == "✨ 북큐레이션 추천":
    st.title("✨ 오늘의 특별한 북큐레이션")
    if all_topics_data:
        theme = random.choice(list(all_topics_data.keys()))
        st.markdown(f"<div style='background-color: #FFF0F5; padding: 10px; border-radius: 15px; margin-bottom:20px;'><h3>🎨 오늘의 테마: {theme}</h3></div>", unsafe_allow_html=True)
        df = all_topics_data[theme]
        if not df.empty:
            book = df.sample(n=1).iloc[0]
            st.markdown(f"""
            <div class="info-card" style="text-align: center; border-left: 12px solid #FFB6C1;">
                <h2 style="margin-bottom:10px;">📖 {book.iloc[2]}</h2>
                <p>👤 저자/출판: {book.iloc[3]} / {book.iloc[4]}</p>
                <p style="color: #FFB6C1; font-size: 1.25em; font-weight: bold;">📍 청구기호: {book.iloc[1]}</p>
                <hr style="border: 0.5px solid #eee;">
                <p style="font-style: italic;">"이 책과 함께라면 오늘 하루가 더 행복해질 거예요! ✨"</p>
            </div>
            """, unsafe_allow_html=True)

elif menu == "🎀 Aily에 대해":
    st.title("🎀 안녕! 나는 사서 Aily야")
    st.markdown(f"""
    <div class="info-card">
        <h3 style="margin-top:0;">📋 나의 프로필</h3>
        <ul style="list-style-type: '🐰 '; line-height: 1.8;">
            <li><b>자기소개:</b> 2026년 3월 입사한 <b>파릇파릇 신입 사서</b>!</li>
            <li><b>MBTI:</b> <b>ESFJ</b> (친절 싹싹 심곡도서관 비타민!)</li>
            <li><b>혈액형:</b> B형 / <b>생일:</b> 4.23</li>
            <li><b>별자리:</b> 황소자리 ♉</li>
        </ul>
    </div>
    <div class="info-card" style="background-color: #FFF0F5;">
        <h3 style="margin-top:0;">🏫 우리 심곡도서관은?</h3>
        <p>인천 서구 시설관리공단에서 운영하는 <b>심곡도서관</b>은 여러분의 따뜻한 쉼터예요. 
        신입 사서 Aily가 늘 기다리고 있을게요! 🌸</p>
    </div>
    """, unsafe_allow_html=True)

elif menu == "📚 주제별 책 추천":
    st.title("📚 어떤 책을 읽어볼까요?")
    if all_topics_data:
        topics = list(all_topics_data.keys())
        selected_topic = st.selectbox("관심 주제를 선택해 주세요!", topics)
        if st.button("Aily의 추천 받기 🎁"):
            df = all_topics_data[selected_topic]
            for _, row in df.sample(n=min(3, len(df))).iterrows():
                st.markdown(f"""
                <div class="info-card" style="border-left: 12px solid #FFB6C1;">
                    <h3 style="text-align: left; margin-top:0;">📖 {row.iloc[2]}</h3>
                    <p style="font-size: 0.9em; margin-bottom: 5px;">👤 {row.iloc[3]} / {row.iloc[4]}</p>
                    <p style="color: #FFB6C1; font-weight: bold; margin-bottom: 0;">📍 청구기호: {row.iloc[1]}</p>
                </div>
                """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # 메인 컨테이너 끝

import streamlit as st
import pandas as pd
import random
import base64

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="심곡도서관 AILY 북큐레이션", page_icon="📖", layout="centered")

# --- 배경 이미지 및 귀여운 폰트 설정 ---
def get_base64(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return None

# 배경 이미지 (aily1.png) 적용 및 가독성 패치
bin_str = get_base64('aily1.png')
bg_style = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Brush+Script&display=swap');
    
    .stApp {{
        background-image: url("data:image/png;base64,{bin_str if bin_str else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}
    .stApp::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        background-color: rgba(255, 253, 248, 0.9); /* 가독성을 위한 90% 불투명 덮개 */
        z-index: -1;
    }}
    
    /* 전체 폰트 적용 */
    html, body, [class*="css"] {{
        font-family: 'Nanum Brush Script', cursive !important;
        font-size: 1.4em;
        color: #4A3F35;
    }}
    
    /* 제목 및 카드 디자인 */
    .title-text {{
        color: #FFB6C1;
        font-size: 3em;
        text-align: center;
        margin-bottom: 10px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }}
    
    .curation-card {{
        background-color: white;
        padding: 30px;
        border-radius: 30px;
        border: 3px dashed #FFB6C1;
        box-shadow: 0 10px 20px rgba(255, 182, 193, 0.15);
        margin-top: 20px;
    }}
    </style>
"""
st.markdown(bg_style, unsafe_allow_html=True)

# 2. 데이터 로드 함수
@st.cache_data
def load_data(file_name):
    try:
        return pd.read_excel(file_name, sheet_name=None)
    except:
        return None

# --- 메인 북큐레이션 영역 ---
st.markdown('<h1 class="title-text">✨ Aily의 북큐레이션 ✨</h1>', unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2em;'>심곡도서관 사서 Aily가 정성껏 고른 오늘의 테마 도서입니다.</p>", unsafe_allow_html=True)

all_topics_data = load_data('학습데이터.xlsx')

if all_topics_data:
    # 1. 랜덤하게 테마(주제) 하나 선정
    topics = list(all_topics_data.keys())
    
    # 세션 상태를 이용해 '새로고침' 전까지는 같은 테마를 유지하게 함 (사용자 경험 개선)
    if 'current_theme' not in st.session_state:
        st.session_state.current_theme = random.choice(topics)
    
    theme = st.session_state.current_theme
    
    st.markdown(f"""
        <div style='background-color: #FFF0F5; padding: 15px; border-radius: 20px; text-align: center; margin: 20px 0;'>
            <h2 style='margin: 0; color: #FF99AA;'>🎨 오늘의 추천 테마: [{theme}]</h2>
        </div>
    """, unsafe_allow_html=True)

    # 2. 해당 테마에서 도서 추천 (최대 3권)
    df = all_topics_data[theme]
    if not df.empty:
        num_books = min(3, len(df))
        recommended = df.sample(n=num_books)
        
        for _, row in recommended.iterrows():
            try:
                reg_num, call_num, title, author, pub = row.iloc[0], row.iloc[1], row.iloc[2], row.iloc[3], row.iloc[4]
            except:
                reg_num = call_num = title = author = pub = "정보 없음"
            
            st.markdown(f"""
                <div class="curation-card">
                    <h2 style="color: #FFB6C1; margin-bottom: 10px;">📖 {title}</h2>
                    <p style="font-size: 0.9em; color: #777;">👤 저자/발행: {author} / {pub}</p>
                    <div style="background-color: #FFF5F7; padding: 15px; border-radius: 15px; border-left: 8px solid #FFB6C1;">
                        <p style="margin: 0; font-weight: bold; font-size: 1.1em; color: #4A3F35;">📍 청구기호: {call_num}</p>
                        <p style="margin: 5px 0 0 0; font-size: 0.8em; color: #999;">🔖 등록번호: {reg_num}</p>
                    </div>
                    <p style="margin-top: 15px; font-style: italic; color: #8E6E53;">
                        👩‍🏫 "사서 Aily가 이 책을 {theme} 테마의 도서로 선정한 이유는, 우리 삶에 꼭 필요한 통찰력을 주기 때문이에요. 지금 심곡도서관 서가에서 만나보세요!"
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
    # 3. 다른 테마 보기 버튼
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 다른 테마 추천받기"):
        st.session_state.current_theme = random.choice(topics)
        st.rerun()

    st.divider()
    st.caption("※ 이미 대출 중일 수 있으니 도서관 홈페이지를 꼭 확인해 주세요! 😅")
    
else:
    st.error("학습데이터.xlsx 파일을 찾을 수 없습니다.")

# 사이드바는 깔끔하게 이미지와 로고만 배치
with st.sidebar:
    try:
        st.image("aily2.png", use_container_width=True)
    except: pass
    st.markdown("<h3 style='text-align: center;'>심곡도서관 신입사서 Aily</h3>", unsafe_allow_html=True)
    st.write("2026.03 입사 / ESFJ / B형")

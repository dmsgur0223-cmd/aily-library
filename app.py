import streamlit as st
import pandas as pd
import random 

# 1. 웹 페이지 기본 설정 (탭 아이콘 변경)
st.set_page_config(page_title="AILY 도서 추천", page_icon="🐰")

image_list = ["aily1.png", "aily2.png"]
selected_image = random.choice(image_list)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image(selected_image, use_container_width=True)
    except FileNotFoundError:
        st.warning("이미지 파일을 찾을 수 없습니다. 'aily1.png', 'aily2.png' 파일이 있는지 확인해주세요!")

# 2. 화면 제목 및 부제목 변경
st.title("🐰 심곡도서관 보조사서 AILY")
st.subheader("관심 있는 주제를 고르면 책을 추천해 드립니다!")

# ★ 새로 추가된 안내 문구 (st.caption을 쓰면 안내사항처럼 작고 깔끔하게 나옵니다)
st.caption("※ 이미 대출중일수도 있어요! 😅") 

st.divider() 

def load_data(file_name):
    return pd.read_excel(file_name, sheet_name=None)

file_path = '학습데이터.xlsx'

try:
    all_topics_data = load_data(file_path)
    topics = list(all_topics_data.keys())
    
    selected_topic = st.selectbox("어떤 주제의 책을 찾으시나요?", topics)
    
    if st.button(f"'{selected_topic}' 책 추천받기 🎁"):
        df = all_topics_data[selected_topic]
        
        if df.empty:
            st.warning(f"앗! '{selected_topic}' 주제에 추천할 도서가 아직 비어있습니다. 😅")
        else:
            num_books = min(3, len(df))
            recommended = df.sample(n=num_books)
            
            # 3. 추천 완료 메시지 변경
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
                
except FileNotFoundError:
    st.error("엑셀 파일을 찾을 수 없습니다. '학습데이터.xlsx' 파일이 있는지 확인해주세요.")

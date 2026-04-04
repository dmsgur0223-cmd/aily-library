import streamlit as st
import pandas as pd
import random

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="AILY 도서 추천", page_icon="🐰")

# 데이터 로드 함수
@st.cache_data # 데이터를 매번 새로 읽지 않도록 캐싱합니다
def load_data(file_name):
    try:
        return pd.read_excel(file_name, sheet_name=None)
    except FileNotFoundError:
        return None

file_path = '학습데이터.xlsx'
all_topics_data = load_data(file_path)

# 사이드바 설정 (Gemini 왼쪽 메뉴 느낌)
with st.sidebar:
    st.title("🐰 AILY 설정")
    image_list = ["aily1.png", "aily2.png"]
    try:
        st.image(random.choice(image_list), use_container_width=True)
    except:
        pass
    st.divider()
    st.caption("심곡도서관 보조사서 AILY")
    st.caption("※ 이미 대출 중일 수도 있어요! 😅")

# 메인 화면 제목
st.title("📚 AI 사서 AILY")

# 2. 채팅 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 심곡도서관 보조사서 **AILY**입니다. 어떤 주제의 책을 추천해 드릴까요?"}
    ]

# 3. 기존 채팅 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. 입력창 및 추천 로직
if all_topics_data:
    topics = list(all_topics_data.keys())
    
    # 채팅 하단에 주제 선택 버튼(또는 입력창) 배치
    selected_topic = st.selectbox("추천받고 싶은 주제를 선택하세요:", ["선택안함"] + topics)

    if selected_topic != "선택안함":
        # 사용자 메시지 표시
        user_input = f"'{selected_topic}' 주제의 책을 추천해줘!"
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # AI 추천 로직 가동
        with st.chat_message("assistant"):
            with st.spinner('AILY가 서가에서 책을 찾는 중...'):
                df = all_topics_data[selected_topic]
                
                if df.empty:
                    response = f"앗! '{selected_topic}' 주제는 아직 비어있네요. 😅"
                    st.warning(response)
                else:
                    num_books = min(3, len(df))
                    recommended = df.sample(n=num_books)
                    
                    response = f"**{selected_topic}** 주제에서 좋아하실 만한 책들을 찾아왔어요! ❤️"
                    st.markdown(response)
                    
                    for _, row in recommended.iterrows():
                        try:
                            # 기존 코드의 데이터 인덱싱 유지
                            reg_num, call_num, title, author, pub = row.iloc[0], row.iloc[1], row.iloc[2], row.iloc[3], row.iloc[4]
                        except:
                            reg_num, call_num, title, author, pub = "정보없음", "정보없음", "정보없음", "정보없음", "정보없음"
                        
                        book_info = f"""
---
📖 **{title}**
👤 저자/발행: {author} / {pub}
📍 청구기호: **{call_num}**
🔖 등록번호: {reg_num}
"""
                        st.info(book_info)
                        response += book_info # 전체 대화 기록 저장을 위해 합침

        # 대화 기록 저장
        st.session_state.messages.append({"role": "assistant", "content": response})
else:
    st.error("엑셀 파일을 찾을 수 없습니다. '학습데이터.xlsx' 파일이 있는지 확인해주세요.")

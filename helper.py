import os

import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()

st.title("챗봇")

# 키 값은 화면에 보여주지 않고, 채워져 있는지만 알려준다
if os.getenv("GEMINI_API_KEY", "").strip():
    st.write("GEMINI_API_KEY가 채워져 있습니다")
else:
    st.write("GEMINI_API_KEY가 비어 있습니다")

question = st.text_input("질문")

if st.button("보내기"):
    if not question.strip():
        st.warning("보낼 말을 넣어 주세요")
    else:
        try:
            # genai.Client()는 GEMINI_API_KEY 환경 변수에서 키를 읽는다
            # 서버가 붐빌 때 화면이 멈춰 있지 않도록 60초(60000ms) 뒤에는 포기한다
            client = genai.Client(http_options={"timeout": 60000})
            interaction = client.interactions.create(
                model="gemini-3.5-flash-lite",
                input=question,
            )
            st.write(interaction.output_text)
            st.write(f"사용한 토큰: {interaction.usage.total_tokens}")
        except Exception as e:
            st.error(f"답을 받지 못했습니다: {e}")

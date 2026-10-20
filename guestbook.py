import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="방명록")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

st.title("방명록")

# 남기는 자리 (남기면 칸이 비워짐)
with st.form("write", clear_on_submit=True):
    content = st.text_input("한 줄 남기기")
    submitted = st.form_submit_button("남기기", type="primary", width="stretch")

if submitted:
    if not content.strip():
        st.warning("내용을 넣어 주세요")
    else:
        supabase.table("guestbook").insert({"message": content.strip()}).execute()

st.divider()

# 쌓인 글 (최근 글이 위)
rows = supabase.table("guestbook").select("*").order("created_at", desc=True).execute().data

if not rows:
    st.caption("아직 남긴 글이 없습니다")
for row in rows:
    with st.container(border=True):
        st.write(row["message"])
        st.caption(row["created_at"][:16].replace("T", " "))

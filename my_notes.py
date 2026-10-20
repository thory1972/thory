import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="내 메모")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

st.title("내 메모")

# 적는 자리 (저장하면 칸이 비워짐)
with st.form("write", clear_on_submit=True):
    content = st.text_input("한 줄 메모")
    submitted = st.form_submit_button("저장", type="primary", width="stretch")

if submitted:
    if not content.strip():
        st.warning("내용을 넣어 주세요")
    else:
        supabase.table("drafts").insert({"comment": content.strip()}).execute()

st.divider()

# 쌓인 메모 (최근 메모가 위)
rows = supabase.table("drafts").select("*").order("created_at", desc=True).execute().data

if not rows:
    st.caption("아직 저장한 메모가 없습니다")
for row in rows:
    with st.container(border=True):
        st.write(row["comment"])
        st.caption(row["created_at"][:16].replace("T", " "))

import os
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="사진 보관함")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# 그림은 Storage 의 photos 버킷에 둔다 (공개 버킷이라 공개 링크로 바로 보인다)
bucket = supabase.storage.from_("photos")

st.title("사진 보관함")

# 올리는 자리 (여러 장을 한꺼번에 고를 수 있고, 올리면 칸은 비워짐)
with st.form("upload", clear_on_submit=True):
    files = st.file_uploader(
        "그림 올리는 칸", type=["png", "jpg", "jpeg", "gif", "webp"], accept_multiple_files=True
    )
    submitted = st.form_submit_button("올리기", type="primary", width="stretch")

if submitted:
    if not files:
        st.warning("그림을 골라 주세요")
    else:
        try:
            for file in files:
                # Storage 는 한글 파일 이름을 받지 않으므로 "올린 때-무작위 8자리.확장자" 로 새로 이름을 붙인다
                name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}{Path(file.name).suffix.lower()}"
                bucket.upload(name, file.getvalue(), {"content-type": file.type})
            st.session_state.uploaded = True
            st.rerun()
        except Exception as e:
            st.error(f"올리지 못했습니다: {e}")

if st.session_state.pop("uploaded", False):
    st.success("올렸습니다")

# 올라온 그림 (최근 것이 위, 버킷이 비면 Storage 가 넣어 두는 빈 자리 표시 파일은 뺀다)
try:
    items = bucket.list("", {"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}})
    items = [i for i in items if i.get("id") and i["name"] != ".emptyFolderPlaceholder"]
except Exception as e:
    st.error(f"그림을 불러오지 못했습니다: {e}")
    st.stop()

left, right = st.columns([3, 1])
left.subheader("올라온 그림")
right.caption(f"{len(items)}장")

if not items:
    st.caption("아직 올라온 그림이 없습니다")

# 한 줄에 3장 (올린 때는 Storage 가 세계 표준시로 주므로 한국 시간으로 바꿔 보여 준다)
for start in range(0, len(items), 3):
    for col, item in zip(st.columns(3), items[start:start + 3]):
        with col.container(border=True):
            st.image(bucket.get_public_url(item["name"]))
            when = pd.to_datetime(item["created_at"], utc=True).tz_convert("Asia/Seoul")
            st.caption(f"{when:%Y-%m-%d %H:%M}")

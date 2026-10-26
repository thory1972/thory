import base64
import os
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="문서 보관함")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# 문서는 Storage 의 docs 버킷에 둔다 (비공개 버킷이라 내려받을 때는 1분(60초)짜리 링크를 만들어 쓴다)
bucket = supabase.storage.from_("docs")
LINK_MINUTES = 1


# Storage 는 한글 파일 이름을 받지 않으므로, 원래 이름을 영문·숫자로 바꿔 저장 이름 뒤에 붙여 둔다
# 저장 이름 = "올린 때-무작위 8자리--원래 이름(바꾼 것)"
def stored_name(original):
    code = base64.urlsafe_b64encode(original.encode("utf-8")).decode().rstrip("=")
    return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}--{code}"


# 저장 이름에서 원래 이름을 되살린다 (이 화면 말고 다른 곳에서 올린 문서는 저장 이름을 그대로 보여 준다)
def original_name(stored):
    _, sep, code = stored.partition("--")
    if not sep:
        return stored
    try:
        return base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)).decode("utf-8")
    except ValueError:
        return stored


st.title("문서 보관함")

# 올리는 자리 (여러 개를 한꺼번에 고를 수 있고, 올리면 칸은 비워짐)
with st.form("upload", clear_on_submit=True):
    files = st.file_uploader("문서 올리는 칸", accept_multiple_files=True)
    submitted = st.form_submit_button("올리기", type="primary", width="stretch")

if submitted:
    if not files:
        st.warning("문서를 골라 주세요")
    else:
        try:
            for file in files:
                # 한글(hwp)처럼 종류를 모르는 문서는 그냥 파일로 올린다
                bucket.upload(
                    stored_name(file.name), file.getvalue(), {"content-type": file.type or "application/octet-stream"}
                )
            st.session_state.uploaded = True
            st.rerun()
        except Exception as e:
            st.error(f"올리지 못했습니다: {e}")

if st.session_state.pop("uploaded", False):
    st.success("올렸습니다")

# 올라온 문서 (최근 것이 위, 버킷이 비면 Storage 가 넣어 두는 빈 자리 표시 파일은 뺀다)
# 내려받기 링크는 화면을 그릴 때마다 새로 만들고, 받을 때 원래 이름으로 저장되게 한다
try:
    items = bucket.list("", {"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}})
    items = [i for i in items if i.get("id") and i["name"] != ".emptyFolderPlaceholder"]
    links = [
        bucket.create_signed_url(i["name"], LINK_MINUTES * 60, {"download": original_name(i["name"])})["signedURL"]
        for i in items
    ]
except Exception as e:
    st.error(f"문서를 불러오지 못했습니다: {e}")
    st.stop()

left, right = st.columns([3, 1])
left.subheader("올라온 문서")
right.caption(f"{len(items)}개")

if not items:
    st.caption("아직 올라온 문서가 없습니다")
else:
    st.caption(f"내려받기 링크는 {LINK_MINUTES}분 동안만 열립니다")

# 한 줄에 하나 (올린 때는 Storage 가 세계 표준시로 주므로 한국 시간으로 바꿔 보여 준다)
for item, link in zip(items, links):
    with st.container(border=True):
        name_col, when_col, link_col = st.columns([3, 2, 1.3], vertical_alignment="center")
        name_col.write(original_name(item["name"]))
        when = pd.to_datetime(item["created_at"], utc=True).tz_convert("Asia/Seoul")
        when_col.caption(f"{when:%Y-%m-%d %H:%M}")
        link_col.link_button("내려받기", link, width="stretch")

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="구독 정리함")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

COLUMNS = ["name", "category", "monthly_fee", "last_used"]
REQUIRED = ["name", "category", "monthly_fee"]

# subscriptions 표 (id 순서, 줄 위치로 어느 줄을 고쳤는지 찾으므로 순서가 늘 같아야 한다)
rows = supabase.table("subscriptions").select("*").order("id").execute().data
subs = pd.DataFrame(rows, columns=["id"] + COLUMNS)
subs["last_used"] = pd.to_datetime(subs["last_used"]).dt.date

st.title("구독 정리함")

# 구독 수, 한 달 합계 (Supabase 에 저장된 것 기준)
count_col, total_col = st.columns(2)
count_col.metric("구독 수", f"{len(subs)}개")
total_col.metric("한 달 합계", f"{int(subs['monthly_fee'].sum()):,}원")

# 저장한 뒤에는 표 칸을 새로 만들어야 고친 흔적이 남지 않으므로, 저장할 때마다 key 를 바꾼다
if "editor_no" not in st.session_state:
    st.session_state.editor_no = 0
key = f"subs_{st.session_state.editor_no}"

# 표 (칸을 눌러 고치고, 맨 아래 빈 줄에 새 줄을 넣고, 줄 왼쪽을 골라 지운다. id 는 보이지 않음)
st.data_editor(
    subs,
    key=key,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_order=COLUMNS,
    column_config={
        "name": st.column_config.TextColumn("이름"),
        "category": st.column_config.TextColumn("분류"),
        "monthly_fee": st.column_config.NumberColumn("한 달 요금", min_value=0, step=1, format="%d"),
        "last_used": st.column_config.DateColumn("마지막으로 쓴 날", format="YYYY-MM-DD"),
    },
)

# 다 됐다는 알림 (저장·고치기·지우기 중 방금 한 곳 아래에 한 번 보여 준다)
def notice(place):
    if st.session_state.get("done", (None,))[0] == place:
        st.success(st.session_state.pop("done")[1])


# 다 된 뒤 알림을 남기고, 표 칸을 새로 만들어 처음부터 다시 그린다
def finish(place, message):
    st.session_state.done = (place, message)
    st.session_state.editor_no += 1
    st.rerun()


# 빈 칸 찾기 (새 줄은 꼭 넣을 칸이 다 있어야 하고, 고친 줄은 꼭 넣을 칸을 비우면 안 된다)
def empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def has_empty(changes):
    added = changes["added_rows"]
    edited = changes["edited_rows"].values()
    return any(empty(row.get(c)) for row in added for c in REQUIRED) or any(
        c in row and empty(row[c]) for row in edited for c in REQUIRED
    )


# 저장 (지우기 → 고치기 → 넣기 순서로 subscriptions 표에 반영)
if st.button("저장", type="primary", width="stretch"):
    changes = st.session_state[key]
    if has_empty(changes):
        st.warning("이름·분류·한 달 요금을 모두 넣어 주세요")
    else:
        try:
            for i in changes["deleted_rows"]:
                supabase.table("subscriptions").delete().eq("id", int(subs.iloc[i]["id"])).execute()
            for i, row in changes["edited_rows"].items():
                supabase.table("subscriptions").update(row).eq("id", int(subs.iloc[int(i)]["id"])).execute()
            if changes["added_rows"]:
                added = [{c: row.get(c) for c in COLUMNS} for row in changes["added_rows"]]
                supabase.table("subscriptions").insert(added).execute()
            finish("save", "저장했습니다")
        except Exception as e:
            st.error(f"저장하지 못했습니다: {e}")
notice("save")


# 구독 고르기 (이름이 같은 구독이 있어도 헷갈리지 않게 줄 위치로 고른다)
def pick(label):
    i = st.selectbox(label, range(len(subs)), format_func=lambda i: subs.iloc[i]["name"])
    return subs.iloc[i]


# 표가 비어 있으면 고르고 고칠 것이 없으므로 상자를 그리지 않는다
if not subs.empty:
    # 고치기 상자 (고른 구독의 지금 값이 칸에 미리 들어가 있다)
    with st.container(border=True):
        st.subheader("고치기")
        row = pick("고칠 구독")
        no = int(row["id"])
        name = st.text_input("이름", row["name"], key=f"edit_name_{no}")
        category = st.text_input("분류", row["category"], key=f"edit_category_{no}")
        fee = st.number_input("한 달 요금", min_value=0, step=1, value=int(row["monthly_fee"]), key=f"edit_fee_{no}")
        last_used = st.date_input(
            "마지막으로 쓴 날", None if pd.isna(row["last_used"]) else row["last_used"], key=f"edit_last_used_{no}"
        )
        if st.button("고치기", type="primary", width="stretch"):
            if empty(name) or empty(category) or fee is None:
                st.warning("이름·분류·한 달 요금을 모두 넣어 주세요")
            else:
                try:
                    supabase.table("subscriptions").update(
                        {
                            "name": name.strip(),
                            "category": category.strip(),
                            "monthly_fee": int(fee),
                            "last_used": last_used.isoformat() if last_used else None,
                        }
                    ).eq("id", no).execute()
                    finish("edit", "고쳤습니다")
                except Exception as e:
                    st.error(f"저장하지 못했습니다: {e}")
        notice("edit")

    # 지우기 상자
    with st.container(border=True):
        st.subheader("지우기")
        row = pick("지울 구독")
        if st.button("지우기", type="primary", width="stretch"):
            try:
                supabase.table("subscriptions").delete().eq("id", int(row["id"])).execute()
                finish("delete", "지웠습니다")
            except Exception as e:
                st.error(f"저장하지 못했습니다: {e}")
        notice("delete")

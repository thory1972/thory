from pathlib import Path

import pandas as pd
import streamlit as st

# 읽을 파일 (이 파일 옆 data 폴더)
CSV_PATH = Path(__file__).parent / "data" / "56_practice-inquiries.csv"

df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

# 필터 (type 열, 처음에는 모든 값을 골라 둠)
types = list(df["type"].unique())
picked = st.multiselect("type", types, default=types)

# 필터 (status 열, 처음에는 모든 값을 골라 둠)
statuses = list(df["status"].unique())
picked_status = st.multiselect("status", statuses, default=statuses)

# 두 필터에 모두 맞는 줄만
shown = df[df["type"].isin(picked) & df["status"].isin(picked_status)]

# 지금 보이는 줄 수
st.write(len(shown))

# 표
st.dataframe(shown, hide_index=True, width="stretch")

# 내려받기 (지금 표에 보이는 줄만, 엑셀에서도 한글이 안 깨지게 utf-8-sig)
st.download_button(
    "내려받기",
    shown.to_csv(index=False).encode("utf-8-sig"),
    file_name="practice-inquiries-filtered.csv",
    mime="text/csv",
)

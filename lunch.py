import os
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# 카카오 로컬 API (https://developers.kakao.com/docs/ko/local/dev-guide)
ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
NAVER_SEARCH_URL = "https://map.naver.com/p/search/"
DEFAULT_CENTER = "전주 객사"
FOOD_CODE = "FD6"  # 카테고리 그룹 코드: 음식점
MAX_PAGES = 3  # 한 쪽에 최대 15개, 넘겨 볼 수 있는 결과는 최대 45개(pageable_count)

# 찾을 음식 종류 (첫 줄은 음식점 전체, 나머지는 카카오 분류 이름 그대로 키워드로 쓴다)
KINDS = ["음식점 전체", "한식", "중식", "일식", "양식", "분식", "치킨", "패스트푸드"]

SORTS = {
    "가까운 순": ("거리(m)", True),
    "이름순": ("이름", True),
    "종류순": ("종류", True),
}


def kakao_get(url, params):
    # 키는 화면에 보여주지 않고 머리글에만 담는다
    key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    res = requests.get(
        url,
        headers={"Authorization": f"KakaoAK {key}"},
        params=params,
        timeout=10,
    )
    # 실패하면 카카오가 돌려준 까닭(message)을 그대로 보여준다
    if not res.ok:
        try:
            reason = res.json().get("message", res.text)
        except ValueError:
            reason = res.text
        raise RuntimeError(f"{res.status_code} {reason}")
    return res.json()


def find_center(place):
    # 기준 장소의 좌표를 카카오에서 찾는다. 이름·주소는 카카오가 돌려준 값만 쓴다
    # 1) 주소 검색 결과가 딱 하나면 그 동네 (예: "전주 서신동")
    #    "효자동"처럼 여러 지역이 나오면 어느 곳인지 정할 수 없으니 쓰지 않는다
    addr = kakao_get(ADDRESS_URL, {"query": place, "size": 2})["documents"]
    if len(addr) == 1:
        return {"name": addr[0]["address_name"], "address": "", "x": addr[0]["x"], "y": addr[0]["y"]}
    # 2) 아니면 키워드 검색 첫 결과 (역·건물·명소 등)
    docs = kakao_get(KEYWORD_URL, {"query": place, "size": 1})["documents"]
    if docs:
        d = docs[0]
        return {"name": d["place_name"], "address": d["road_address_name"] or d["address_name"], "x": d["x"], "y": d["y"]}
    return None


def search_food(center, keyword, radius):
    x, y = center["x"], center["y"]
    params = {
        "category_group_code": FOOD_CODE,
        "x": x,
        "y": y,
        "radius": radius,
        "sort": "distance",
        "size": 15,
    }
    # 검색어가 있으면 키워드 검색(음식점만), 비우면 음식점 카테고리 전체
    if keyword:
        url = KEYWORD_URL
        params["query"] = keyword
    else:
        url = CATEGORY_URL

    places = []
    for page in range(1, MAX_PAGES + 1):
        data = kakao_get(url, {**params, "page": page})
        places += data["documents"]
        if data["meta"]["is_end"]:
            break
    # 반경 밖 가게는 빼 둔다 (radius 로 이미 걸러지지만 한 번 더)
    return [p for p in places if int(p["distance"] or 0) <= radius]


def to_table(places):
    rows = [
        {
            "이름": p["place_name"],
            # "음식점 > 한식 > 비빔밥" 에서 두 번째 칸(큰 종류)만
            "종류": (p["category_name"].split(" > ") + ["기타", "기타"])[1],
            "거리(m)": int(p["distance"] or 0),
            "전화": p["phone"],
            "주소": p["road_address_name"] or p["address_name"],
            "링크": p["place_url"],
            # 네이버 지도 검색: 가게 이름 + 도로명 주소 (도로명 주소가 없으면 이름만)
            "네이버": NAVER_SEARCH_URL + quote(f"{p['place_name']} {p['road_address_name']}".strip()),
            "lat": float(p["y"]),
            "lon": float(p["x"]),
        }
        for p in places
    ]
    return pd.DataFrame(rows)


st.title("근처 맛집")

place = st.text_input("기준 장소 (역이나 동네 이름)", value=DEFAULT_CENTER)
kind = st.selectbox("찾을 음식 종류", KINDS)
food = st.text_input("찾을 음식 (예: 비빔밥, 비우면 위 종류로)")
radius = st.slider("반경 (m)", 100, 5000, 500, step=100)

# 검색 버튼을 눌렀을 때만 API를 부르고, 결과는 session_state 에 남겨 둔다
if st.button("검색"):
    # 직접 넣은 음식이 우선, 비우면 고른 종류 (음식점 전체면 키워드 없이)
    keyword = food.strip() or ("" if kind == KINDS[0] else kind)
    # 새 검색이 실패하면 지난 결과가 이번 결과처럼 보이지 않도록 먼저 지운다
    for k in ("lunch", "lunch_center", "lunch_radius"):
        st.session_state.pop(k, None)
    if not os.getenv("KAKAO_REST_API_KEY", "").strip():
        st.error("KAKAO_REST_API_KEY가 비어 있습니다")
    elif not place.strip():
        st.error("기준 장소를 넣어 주세요")
    else:
        try:
            center = find_center(place.strip())
            if center is None:
                st.error(f"'{place.strip()}'에 맞는 장소를 찾지 못했습니다")
            else:
                st.session_state["lunch"] = to_table(search_food(center, keyword, radius))
                st.session_state["lunch_center"] = center
                st.session_state["lunch_radius"] = radius
        except Exception as e:
            st.error(f"검색하지 못했습니다: {e}")

if "lunch" not in st.session_state:
    st.info("검색 버튼을 누르면 결과가 나옵니다")
    st.stop()

# 기준 장소: 카카오가 돌려준 이름·주소 그대로 (동네는 주소가 곧 이름)
center = st.session_state["lunch_center"]
if center["address"]:
    st.write(f"기준 장소: {center['name']} · {center['address']}")
else:
    st.write(f"기준 장소: {center['name']}")

df = st.session_state["lunch"]
if df.empty:
    st.info("결과가 없습니다")
    st.stop()

st.write(f"찾은 가게 {len(df)}곳")

# 음식점 지도: 파란 점 = 가게, 주황 점·원 = 기준 장소와 검색 반경
# 점에 마우스를 올리면 가게 이름·종류·거리가 보인다
c_lat, c_lon = float(center["y"]), float(center["x"])
r = st.session_state["lunch_radius"]
spots = df.assign(tip=df["이름"] + "\n" + df["종류"] + " · " + df["거리(m)"].astype(str) + "m")
mid = pd.DataFrame([{"lat": c_lat, "lon": c_lon, "tip": center["name"]}])
# 반경이 넓을수록 멀리서 본다
zoom = 15 if r <= 700 else 14 if r <= 1500 else 13 if r <= 3000 else 12
st.pydeck_chart(
    pdk.Deck(
        initial_view_state=pdk.ViewState(latitude=c_lat, longitude=c_lon, zoom=zoom),
        layers=[
            # 검색 반경 (테두리만)
            pdk.Layer(
                "ScatterplotLayer", mid, get_position="[lon, lat]", get_radius=r,
                filled=False, stroked=True, get_line_color=[234, 88, 12, 160], line_width_min_pixels=2,
            ),
            pdk.Layer(
                "ScatterplotLayer", spots, get_position="[lon, lat]", get_radius=8,
                radius_min_pixels=5, get_fill_color=[37, 99, 235, 210],
                stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1, pickable=True,
            ),
            pdk.Layer(
                "ScatterplotLayer", mid, get_position="[lon, lat]", get_radius=12,
                radius_min_pixels=7, get_fill_color=[234, 88, 12], pickable=True,
            ),
        ],
        tooltip={"text": "{tip}"},
    )
)

# 정렬 (이미 받아 둔 결과만 다시 줄 세우므로 API를 다시 부르지 않는다)
sort_by = st.selectbox("정렬 기준", list(SORTS))
col, asc = SORTS[sort_by]
shown = df.sort_values(col, ascending=asc)

st.dataframe(
    shown.drop(columns=["lat", "lon"]),
    hide_index=True,
    width="stretch",
    column_config={
        "링크": st.column_config.LinkColumn("링크", display_text="카카오맵"),
        "네이버": st.column_config.LinkColumn("네이버", display_text="네이버 지도"),
    },
)

# 종류별 가게 수 (많은 순)
st.subheader("종류별 가게 수")
counts = df["종류"].value_counts().rename("가게 수")
st.bar_chart(counts, horizontal=True, sort="-가게 수")

# 거리별 가게 수 (검색한 반경을 다섯 구간으로 나눔)
st.subheader("거리별 가게 수")
edges = [r * i // 5 for i in range(6)]
labels = [f"{edges[i]}~{edges[i + 1]}m" for i in range(5)]
bins = pd.cut(df["거리(m)"], edges, labels=labels, include_lowest=True)
st.bar_chart(bins.value_counts().reindex(labels).rename("가게 수"), sort=False)

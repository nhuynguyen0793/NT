import streamlit as st

st.title("🎈 Tour Du lịch Nha Trang")
import streamlit as st
import pandas as pd
import requests
import base64
import folium
from streamlit-folium import st_folium

# ============ CONFIG ============
st.set_page_config(
    page_title="Hành trình Nha Trang",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        div[data-testid="stVerticalBlock"] button[kind="secondary"] {
            background: none;
            border: none;
            padding: 0;
            text-align: left;
            font-weight: 700;
            font-size: 15px;
            box-shadow: none;
        }
        div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
            text-decoration: underline;
            background: none;
        }
    </style>
    """,
    unsafe_allow_html=True
)

TOUR_PATH = "Data/nhatrang_tour.csv"
FOOD_PATH = "Data/nhatrang_food.csv"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"

COLOR_TOUR = "#1565C0"
COLOR_FOOD = "#C2620E"
BANNER_BG = "#DCE9F5"

BUOI_ICON = {
    "Sáng": "🌅",
    "Trưa": "🍽️",
    "Chiều": "🌇",
    "Tối": "🌙",
}


def make_placeholder_svg_datauri(place_name, color):
    initials = "".join([w[0] for w in place_name.split()[:2] if w]).upper()
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="320" height="160">
        <rect width="320" height="160" fill="{color}"/>
        <text x="50%" y="48%" font-size="34" fill="white" font-family="Arial, sans-serif"
              font-weight="bold" text-anchor="middle" dominant-baseline="middle">{initials}</text>
        <text x="50%" y="74%" font-size="12" fill="white" font-family="Arial, sans-serif"
              text-anchor="middle" opacity="0.85">📍 Chưa có ảnh minh họa</text>
    </svg>
    """
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


@st.cache_data
def load_data():
    tour = pd.read_csv(TOUR_PATH)
    food = pd.read_csv(FOOD_PATH)
    return tour, food


@st.cache_data(show_spinner=False)
def get_road_route(coords_list):
    if len(coords_list) < 2:
        return None
    coord_str = ";".join([f"{lon},{lat}" for lat, lon in coords_list])
    url = OSRM_URL.format(coords=coord_str)
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                geom = data["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in geom]
    except requests.exceptions.RequestException:
        pass
    return None


df_tour, df_food = load_data()

# ============ SESSION STATE ============
if "selected_point" not in st.session_state:
    st.session_state.selected_point = None
if "zoom_target" not in st.session_state:
    st.session_state.zoom_target = None  # (lat, lon, zoom)

# ============ TIÊU ĐỀ ============
st.markdown("## 🏖️ Hành trình du lịch Nha Trang – Cam Ranh")

title = df_tour["TITLE"].iloc[0]
subtitle = df_tour["SUBTITLE"].iloc[0]

st.markdown(
    f"""
    <div style="
        background-color:{BANNER_BG};
        border-radius:8px;
        padding:18px 24px;
        margin-top:6px;
        margin-bottom:18px;
    ">
        <div style="font-size:19px; font-weight:800; color:{COLOR_TOUR};">
            {title.upper()}
        </div>
        <div style="margin-top:6px; font-size:14.5px; color:#3a3a3a;">
            {subtitle}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ============ DANH SÁCH ĐIỂM DUY NHẤT TRONG HÀNH TRÌNH ============
unique_points = df_tour.drop_duplicates(subset=["TEN"], keep="first").reset_index(drop=True)
point_order = {name: i + 1 for i, name in enumerate(unique_points["TEN"])}
active_point = st.session_state.selected_point or unique_points["TEN"].iloc[0]

# Vị trí trung tâm bản đồ: nếu có target zoom riêng -> dùng nó, ngược lại tính trung bình toàn tuyến
if st.session_state.zoom_target:
    map_center = st.session_state.zoom_target[:2]
    map_zoom = st.session_state.zoom_target[2]
else:
    map_center = [df_tour["LAT"].mean(), df_tour["LON"].mean()]
    map_zoom = 11

# ============ VÙNG TRÁI: BẢN ĐỒ + VÙNG PHẢI: CHI TIẾT HÀNH TRÌNH ============
col_map, col_info = st.columns([2, 1])

with col_map:
    m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="OpenStreetMap")

    coords_list = list(zip(unique_points["LAT"], unique_points["LON"]))

    # --- Vẽ tuyến đường bộ thực tế nối các điểm hành trình ---
    if len(coords_list) >= 2:
        road_geom = get_road_route(coords_list)
        if road_geom:
            folium.PolyLine(road_geom, color=COLOR_TOUR, weight=4, opacity=0.85).add_to(m)
        else:
            folium.PolyLine(coords_list, color=COLOR_TOUR, weight=3, opacity=0.6, dash_array="6,6").add_to(m)
            st.caption("⚠️ Không lấy được tuyến đường bộ thực tế (OSRM) — đang hiển thị đường nối thẳng tạm thời.")

    # --- Marker cho từng điểm trong hành trình ---
    for idx, row in unique_points.iterrows():
        stops_here = df_tour[df_tour["TEN"] == row["TEN"]]
        stop_lines = "<br>".join(
            f"🕐 {r['GIO']} – {r['HOAT_DONG']}" for _, r in stops_here.iterrows()
        )
        detail_lines = "<br><br>".join(
            str(r["MO_TA_CHI_TIET"]) for _, r in stops_here.iterrows()
            if isinstance(r.get("MO_TA_CHI_TIET"), str) and r["MO_TA_CHI_TIET"].strip()
        )

        is_active = row["TEN"] == active_point
        custom_img = row.get("IMG_URL")
        if isinstance(custom_img, str) and custom_img.strip():
            img_src = custom_img.strip()
        else:
            img_src = make_placeholder_svg_datauri(row["TEN"], COLOR_TOUR)

        popup_html = f"""
        <div style="width:240px;">
            <img src="{img_src}" style="width:100%; height:100px; object-fit:cover; border-radius:6px; margin-bottom:6px;"/>
            <b>{idx+1}. {row['TEN']}</b><br>
            <div style="font-size:12px; margin-top:4px;">{stop_lines}</div>
            {f'<div style="font-size:11.5px; color:#555; margin-top:6px; max-height:90px; overflow-y:auto;">{detail_lines}</div>' if detail_lines else ''}
        </div>
        """

        marker = folium.Marker(
            location=[row["LAT"], row["LON"]],
            tooltip=f"{idx+1}. {row['TEN']}",
            icon=folium.DivIcon(html=f"""
                <div style="
                    background-color:{'#D32F2F' if is_active else COLOR_TOUR};
                    color:white;
                    border-radius:50%;
                    width:{34 if is_active else 30}px;height:{34 if is_active else 30}px;
                    display:flex;align-items:center;justify-content:center;
                    font-weight:bold;font-size:{15 if is_active else 14}px;
                    border:3px solid {'#FFD700' if is_active else 'white'};
                    box-shadow:0 2px 5px rgba(0,0,0,0.5);
                ">{idx+1}</div>
            """)
        )
        folium.Popup(popup_html, max_width=260, show=is_active).add_to(marker)
        marker.add_to(m)

    # --- Marker cho các quán ăn gợi ý (icon khác màu) ---
    for idx, row in df_food.iterrows():
        is_active = row["TEN"] == active_point
        custom_img = row.get("IMG_URL") if "IMG_URL" in df_food.columns else None
        if isinstance(custom_img, str) and custom_img.strip():
            img_src = custom_img.strip()
        else:
            img_src = make_placeholder_svg_datauri(row["TEN"], COLOR_FOOD)

        popup_html = f"""
        <div style="width:220px;">
            <img src="{img_src}" style="width:100%; height:90px; object-fit:cover; border-radius:6px; margin-bottom:6px;"/>
            <b>🍴 {row['TEN']}</b>
        </div>
        """
        marker = folium.Marker(
            location=[row["LAT"], row["LON"]],
            tooltip=f"🍴 {row['TEN']}",
            icon=folium.DivIcon(html=f"""
                <div style="
                    background-color:white;
                    color:{'#D32F2F' if is_active else COLOR_FOOD};
                    border:2px solid {'#D32F2F' if is_active else COLOR_FOOD};
                    border-radius:50%;
                    width:{30 if is_active else 26}px;height:{30 if is_active else 26}px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:14px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.4);
                ">🍴</div>
            """)
        )
        folium.Popup(popup_html, max_width=240, show=is_active).add_to(marker)
        marker.add_to(m)

    st_folium(m, width=None, height=620, key=f"map_{active_point}")

with col_info:
    st.markdown(
        f"""<div style="font-size:18px; font-weight:800; color:{COLOR_TOUR}; margin-bottom:10px;">
        CHI TIẾT HÀNH TRÌNH
        </div>""",
        unsafe_allow_html=True
    )

    with st.container(height=600):
        # --- Danh sách hành trình chính (có số thứ tự) ---
        for idx, row in df_tour.iterrows():
            buoi_icon = BUOI_ICON.get(row["BUOI"], "🕐")
            stop_no = point_order[row["TEN"]]
            is_active = row["TEN"] == active_point

            border_color = "#D32F2F" if is_active else COLOR_TOUR
            bg_color = "rgba(211,47,47,0.06)" if is_active else "transparent"

            col_num, col_content = st.columns([0.12, 0.88])
            with col_num:
                st.markdown(
                    f"""<div style="
                        background-color:{border_color};
                        color:white;
                        border-radius:50%;
                        width:26px;height:26px;
                        display:flex;align-items:center;justify-content:center;
                        font-weight:bold;font-size:13px;
                        margin-top:6px;
                    ">{stop_no}</div>""",
                    unsafe_allow_html=True
                )
            with col_content:
                st.markdown(
                    f"""<div style="font-size:12.5px; color:#888; font-weight:600;">
                        {buoi_icon} {row['BUOI']} ({row['GIO']})
                    </div>""",
                    unsafe_allow_html=True
                )
                # Bấm vào tiêu đề -> bản đồ phóng tới vị trí điểm này
                if st.button(row["TEN"], key=f"title_tour_{idx}"):
                    st.session_state.selected_point = row["TEN"]
                    st.session_state.zoom_target = (row["LAT"], row["LON"], 15)
                    st.rerun()
                st.markdown(
                    f"""<div style="font-size:13.5px; color:#444; margin-top:-6px; margin-bottom:6px;
                        border-left:3px solid {border_color}; background-color:{bg_color};
                        padding:4px 8px; border-radius:4px;">
                        {row['HOAT_DONG']}
                    </div>""",
                    unsafe_allow_html=True
                )
                mo_ta_chi_tiet = row.get("MO_TA_CHI_TIET")
                if isinstance(mo_ta_chi_tiet, str) and mo_ta_chi_tiet.strip():
                    with st.expander("📖 Xem chi tiết hoạt động"):
                        st.markdown(
                            f"""<div style="font-size:13px; color:#555; line-height:1.5;">
                                {mo_ta_chi_tiet}
                            </div>""",
                            unsafe_allow_html=True
                        )
                st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

        # --- Gợi ý ăn uống ---
        st.markdown("---")
        st.markdown(
            f"""<div style="font-size:15px; font-weight:800; color:{COLOR_FOOD}; margin-bottom:8px;">
            🍴 GỢI Ý ĂN UỐNG TẠI NHA TRANG
            </div>""",
            unsafe_allow_html=True
        )
        for idx, row in df_food.iterrows():
            is_active = row["TEN"] == active_point
            border_color = "#D32F2F" if is_active else COLOR_FOOD
            bg_color = "rgba(211,47,47,0.06)" if is_active else "transparent"

            if st.button(f"🍴 {row['TEN']}", key=f"title_food_{idx}"):
                st.session_state.selected_point = row["TEN"]
                st.session_state.zoom_target = (row["LAT"], row["LON"], 15)
                st.rerun()
            st.markdown(
                f"""<div style="border-left:3px solid {border_color}; background-color:{bg_color};
                    padding:2px 8px; border-radius:4px; margin-top:-6px; margin-bottom:8px; font-size:12px; color:#777;">
                    📍 {row['LAT']:.5f}, {row['LON']:.5f}
                </div>""",
                unsafe_allow_html=True
            )

        # --- Nút quay lại toàn cảnh ---
        st.markdown("---")
        if st.button("🔄 Xem toàn bộ hành trình", use_container_width=True):
            st.session_state.zoom_target = None
            st.session_state.selected_point = None
            st.rerun()

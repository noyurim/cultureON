import streamlit as st
import pandas as pd
import random
import calendar
import urllib.parse
import requests
import os
from datetime import date, timedelta
from st_clickable_images import clickable_images

KAKAO_API_KEY = st.secrets["KAKAO_API_KEY"]
NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]

st.set_page_config(page_title="문화ON", page_icon="🏛️", layout="centered")

def get_culture_day():
    today = date.today()
    year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]
    last_date = date(year, month, last_day)
    days_back = (last_date.weekday() - 2) % 7
    return last_date - timedelta(days=days_back)

culture_day = get_culture_day()

@st.cache_data
def get_kakao_images(keyword):
    try:
        url = "https://dapi.kakao.com/v2/search/image"
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        params = {"query": keyword, "size": 10}
        res = requests.get(url, headers=headers, params=params, timeout=4).json()
        candidates = []
        for doc in res.get('documents', []):
            img_url = doc.get('image_url')
            if doc.get('width', 0) >= 150 and doc.get('height', 0) >= 150 and img_url:
                candidates.append(img_url)
        return candidates
    except:
        return []

@st.cache_data
def get_naver_images(keyword):
    try:
        url = "https://openapi.naver.com/v1/search/image"
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        params = {"query": keyword, "display": 10}
        res = requests.get(url, headers=headers, params=params, timeout=4).json()
        candidates = []
        for item in res.get('items', []):
            img_url = item.get('link')
            w = int(item.get('sizewidth', 0) or 0)
            h = int(item.get('sizeheight', 0) or 0)
            if img_url and (w == 0 or (w >= 150 and h >= 150)):
                candidates.append(img_url)
        return candidates
    except:
        return []

@st.cache_data
def get_question_image(keyword):
    candidates = get_naver_images(keyword) + get_kakao_images(keyword)
    return candidates[:4]

SCORE_COL_MAP = {
    ("남성", "15-19세"):   "선호도_남성_15-19세",
    ("남성", "20대"):      "선호도_남성_20대",
    ("남성", "30대"):      "선호도_남성_30대",
    ("남성", "40대"):      "선호도_남성_40대",
    ("남성", "50대"):      "선호도_남성_50대",
    ("남성", "60대"):      "선호도_남성_60대",
    ("남성", "70세 이상"): "선호도_남성_70세 이상",
    ("여성", "15-19세"):   "선호도_여성_15-19세",
    ("여성", "20대"):      "선호도_여성_20대",
    ("여성", "30대"):      "선호도_여성_30대",
    ("여성", "40대"):      "선호도_여성_40대",
    ("여성", "50대"):      "선호도_여성_50대",
    ("여성", "60대"):      "선호도_여성_60대",
    ("여성", "70세 이상"): "선호도_여성_70세 이상",
}

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('final.csv')

        sido_map = {
            '서울': '서울특별시', '경기': '경기도', '인천': '인천광역시',
            '부산': '부산광역시', '대구': '대구광역시', '광주': '광주광역시',
            '대전': '대전광역시', '울산': '울산광역시', '세종': '세종특별자치시',
            '강원특별자치도': '강원특별자치도', '강원': '강원특별자치도',
            '충북': '충청북도', '충남': '충청남도',
            '전북특별자치도': '전라북도', '전북': '전라북도', '전남': '전라남도',
            '경북': '경상북도', '경남': '경상남도',
            '제주특별자치도': '제주특별자치도', '제주': '제주특별자치도',
        }

        def extract_sido_from_address(addr):
            if pd.isna(addr): return '전국'
            first = str(addr).split()[0] if str(addr).split() else ''
            return sido_map.get(first, '전국')

        df['시도'] = df['도로명주소'].apply(extract_sido_from_address)
        df.loc[df['시도'] == '전국', '시도'] = df.loc[df['시도'] == '전국', '지역'].fillna('전국')

        def extract_sigungu(addr):
            if pd.isna(addr): return ''
            parts = str(addr).split()
            return parts[1] if len(parts) > 1 else ''

        df['시군구'] = df['도로명주소'].apply(extract_sigungu)
        df['혜택'] = df['내용'].fillna('상세 혜택은 홈페이지 참조')

        return df

    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df = load_data()

@st.cache_data
def get_sigungu_map():
    result = {}
    for sido, group in df.groupby('시도'):
        sigungu_list = sorted([s for s in group['시군구'].dropna().unique() if s])
        result[sido] = sigungu_list
    return result

sigungu_map = get_sigungu_map()
sido_list = sorted(sigungu_map.keys())

cluster_names = {
    0: "정적/학술형 (도서관, 문학)",
    1: "동적/대중문화형 (영화관, 공연)",
    2: "야외/체험형 (자연, 로컬체험)",
}
cluster_emoji = {0: "📚", 1: "🎬", 2: "🌿"}

# ==========================================
# TYPE_TABLE — main/sub 군집 구조
# main: 메인 군집 (2개 추천)
# sub: 서브 군집 (나머지 채우기)
# ==========================================
TYPE_TABLE = {
    # 혼자 + 실내 + 가성비
    "0000": ("🎧 고요한 탐구자",      "혼자 실내에서 가성비 있게, 익숙한 곳을 즐기는 당신",      {"main": [0], "sub": [2]}),
    "0001": ("📚 사색하는 학자",      "혼자 실내에서 가성비 있게, 로컬 명소를 찾는 당신",       {"main": [0], "sub": [2]}),
    # 혼자 + 실내 + 프리미엄
    "0010": ("🎨 감성 갤러리스트",    "혼자 실내에서 프리미엄하게, 유명한 곳을 즐기는 당신",     {"main": [2], "sub": [1]}),
    "0011": ("🖼️ 은밀한 미식가",     "혼자 실내에서 프리미엄하게, 숨겨진 곳을 찾는 당신",       {"main": [2], "sub": [0]}),
    # 혼자 + 야외 + 가성비
    "0100": ("🌿 힐링 산책자",        "혼자 야외에서 가성비 있게, 익숙한 곳을 즐기는 당신",      {"main": [2], "sub": [0]}),
    "0101": ("🗺️ 로컬 탐험가",       "혼자 야외에서 가성비 있게, 로컬 명소를 찾는 당신",       {"main": [2], "sub": [0]}),
    # 혼자 + 야외 + 프리미엄
    "0110": ("🌲 프리미엄 자연인",     "혼자 야외에서 프리미엄하게, 유명한 곳을 즐기는 당신",     {"main": [2], "sub": [1]}),
    "0111": ("🏕️ 비밀스러운 모험가",  "혼자 야외에서 프리미엄하게, 숨겨진 곳을 찾는 당신",       {"main": [2], "sub": [0]}),
    # 함께 + 실내 + 가성비
    "1000": ("🏛️ 역사 탐방가",       "함께 실내에서 가성비 있게, 익숙한 곳을 즐기는 당신",      {"main": [2], "sub": [0]}),
    "1001": ("👨‍👩‍👧 따뜻한 동반자", "함께 실내에서 가성비 있게, 로컬 명소를 찾는 당신",       {"main": [2], "sub": [1]}),
    # 함께 + 실내 + 프리미엄
    "1010": ("🌟 핫플 문화인",        "함께 실내에서 프리미엄하게, 유명한 곳을 즐기는 당신",     {"main": [1], "sub": [2]}),
    "1011": ("🎭 복합 문화 탐험가",    "함께 실내에서 프리미엄하게, 숨겨진 곳을 찾는 당신",       {"main": [2], "sub": [1]}),
    # 함께 + 야외 + 가성비
    "1100": ("🎵 신나는 공연 메이트",  "함께 야외에서 가성비 있게, 익숙한 곳을 즐기는 당신",      {"main": [1], "sub": [2]}),
    "1101": ("🎪 로컬 액티비티러",     "함께 야외에서 가성비 있게, 로컬 명소를 찾는 당신",       {"main": [2], "sub": [1]}),
    # 함께 + 야외 + 프리미엄
    "1110": ("🎊 활기찬 문화 리더",    "함께 야외에서 프리미엄하게, 유명한 곳을 즐기는 당신",     {"main": [1, 2], "sub": [0]}),
    "1111": ("🎉 만능 문화 탐험가",    "함께 야외에서 프리미엄하게, 숨겨진 곳까지 즐기는 당신",   {"main": [1, 2], "sub": [0]}),
}

questions = [
    {"title": "오늘은 누구와?", "axis": "C",
     "options": {
         "0": {"text": "혼자서 조용히 🎧", "img_keyword": "혼자 책 카페"},
         "1": {"text": "친구/가족과 함께 🎉", "img_keyword": "친구들 모임"}
     }},
    {"title": "어떤 공간이 편해?", "axis": "A",
     "options": {
         "0": {"text": "실내가 좋아 🏛️", "img_keyword": "미술관"},
         "1": {"text": "야외가 좋아 🌿", "img_keyword": "공원 잔디밭"}
     }},
    {"title": "비용은?", "axis": "B",
     "options": {
         "0": {"text": "무료/할인 위주 💚", "img_keyword": "공공 도서관"},
         "1": {"text": "가격 상관없이 특별하게 ✨", "img_keyword": "갤러리 작품"}
     }},
    {"title": "어떤 경험을 원해?", "axis": "A",
     "options": {
         "0": {"text": "보고 감상하는 🎨", "img_keyword": "그림 전시"},
         "1": {"text": "몸으로 체험하는 🎢", "img_keyword": "체험관 놀이"}
     }},
    {"title": "장소 스타일은?", "axis": "D",
     "options": {
         "0": {"text": "유명한 핫플 🏆", "img_keyword": "서울 랜드마크"},
         "1": {"text": "숨겨진 로컬 명소 🗺️", "img_keyword": "골목 카페거리"}
     }},
    {"title": "이동 거리는?", "axis": "D",
     "options": {
         "0": {"text": "가까운 곳이 좋아 🚶", "img_keyword": "동네 거리"},
         "1": {"text": "멀어도 특별한 곳 🚗", "img_keyword": "자동차 여행"}
     }},
    {"title": "선호하는 시간대는?", "axis": "C",
     "options": {
         "0": {"text": "낮에 여유롭게 ☀️", "img_keyword": "맑은 하늘 공원"},
         "1": {"text": "저녁에 감성적으로 🌙", "img_keyword": "도시 야경"}
     }},
    {"title": "문화생활 스타일은?", "axis": "C",
     "options": {
         "0": {"text": "조용히 집중해서 🎯", "img_keyword": "도서관 열람실"},
         "1": {"text": "활기차게 즐기면서 🎊", "img_keyword": "거리 축제"}
     }},
    {"title": "관심 있는 분야는?", "axis": "B",
     "options": {
         "0": {"text": "역사·예술·전통 🏺", "img_keyword": "한옥 마을"},
         "1": {"text": "트렌드·현대·팝컬처 🎬", "img_keyword": "팝업스토어"}
     }},
    {"title": "오늘 하루 마무리는?", "axis": "B",
     "options": {
         "0": {"text": "조용히 여운을 즐기며 🍵", "img_keyword": "찻집 다도"},
         "1": {"text": "맛집이나 카페로 마무리 ☕", "img_keyword": "디저트 카페"}
     }},
]

@st.cache_data
def preload_all_images():
    for q in questions:
        for opt in q['options'].values():
            get_question_image(opt['img_keyword'])

@st.cache_data
def preload_character_images():
    image_bytes = {}
    if os.path.exists("characters"):
        for code in TYPE_TABLE.keys():
            path = f"characters/{code}.png"
            if os.path.exists(path):
                with open(path, "rb") as f:
                    image_bytes[code] = f.read()
    return image_bytes

preload_all_images()
character_images = preload_character_images()

if 'step' not in st.session_state:
    st.session_state.step = 0
if 'answers' not in st.session_state:
    st.session_state.answers = []
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}

def get_culture_type(answers):
    axis_scores = {"A": [], "B": [], "C": [], "D": []}
    for q, a in zip(questions, answers):
        axis_scores[q["axis"]].append(int(a))
    code = ""
    for axis in ["A", "B", "C", "D"]:
        vals = axis_scores[axis]
        avg = sum(vals) / len(vals)
        code += "1" if avg >= 0.5 else "0"
    name, desc, cluster_info = TYPE_TABLE[code]
    return name, desc, cluster_info, code

def get_companion_types(my_code, n=2):
    my_main = set(TYPE_TABLE[my_code][2]["main"])
    scored = []
    for code, (name, desc, cluster_info) in TYPE_TABLE.items():
        if code == my_code:
            continue
        overlap = len(my_main & set(cluster_info["main"]))
        if overlap > 0:
            scored.append((overlap, code, name, desc))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:n]

def safe_get(place, key):
    val = place.get(key, None)
    if val is None or str(val) == 'nan' or str(val).strip() == '':
        return None
    return val

def pick_by_category(pool, n, used_places, used_categories, score_col=None):
    if score_col and score_col in pool.columns:
        pool = pool.sort_values(by=score_col, ascending=False, na_position='last')
    picked = []
    for _, row in pool.iterrows():
        category = str(row.get('구분', '기타'))
        place_name = str(row.get('장소', ''))
        if place_name not in used_places and category not in used_categories:
            used_places.add(place_name)
            used_categories.add(category)
            picked.append(row.to_dict())
        if len(picked) >= n:
            break
    return picked

st.title("🏛️ 문화ON")
st.caption(f"🗓️ 이번 달 문화의날: {culture_day.month}월 {culture_day.day}일 (수)")
st.markdown("---")

if st.session_state.step == 0:
    st.subheader("나만의 문화의날 유형 찾기")
    st.info(f"✨ {len(df):,}개 전국 문화시설 데이터 기반 추천! (16가지 문화 유형)")

    sido = st.selectbox("시/도 선택", sido_list)
    sigungu_options = ["전체"] + sigungu_map.get(sido, [])
    sigungu = st.selectbox("시/군/구 선택", sigungu_options)

    col1, col2 = st.columns(2)
    with col1:
        gender = st.selectbox("성별은?", ["남성", "여성"])
    with col2:
        age = st.selectbox("연령대는?", [
            "15-19세", "20대", "30대", "40대", "50대", "60대", "70세 이상"
        ])

    if st.button("시작하기 →", use_container_width=True):
        st.session_state.user_info = {
            "sido": sido,
            "sigungu": sigungu,
            "gender": gender,
            "age": age,
            "score_col": SCORE_COL_MAP.get((gender, age))
        }
        st.session_state.step = 1
        st.rerun()

elif 1 <= st.session_state.step <= 10:
    current_q = st.session_state.step - 1
    st.progress(st.session_state.step / 10)
    st.caption(f"Q{st.session_state.step} / 10")
    st.markdown(f"### {questions[current_q]['title']}")

    opt_items = list(questions[current_q]['options'].items())
    images, titles = [], []
    for val, opt in opt_items:
        img_candidates = get_question_image(opt['img_keyword'])
        images.append(img_candidates[0] if img_candidates else "https://placehold.co/500x500")
        titles.append(opt['text'])

    clicked = clickable_images(
        images, titles=titles,
        div_style={"display": "flex", "justify-content": "center", "gap": "20px"},
        img_style={"width": "300px", "height": "300px", "object-fit": "cover", "border-radius": "14px"},
        key=f"img_{st.session_state.step}"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div style='text-align:center;font-weight:600'>{titles[0]}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:center;font-weight:600'>{titles[1]}</div>", unsafe_allow_html=True)

    if clicked > -1:
        st.session_state.answers.append(opt_items[clicked][0])
        st.session_state.step += 1
        st.rerun()

elif st.session_state.step == 11:
    type_name, type_desc, cluster_info, my_code = get_culture_type(st.session_state.answers)
    user_info = st.session_state.user_info
    sido = user_info["sido"]
    sigungu = user_info["sigungu"]
    score_col = user_info.get("score_col")
    region_label = f"{sido} {sigungu}" if sigungu != "전체" else sido

    main_clusters = cluster_info["main"]
    sub_clusters = cluster_info["sub"]

    img_col1, img_col2, img_col3 = st.columns([1, 3, 1])
    with img_col2:
        if my_code in character_images:
            st.image(character_images[my_code], use_container_width=True)

    st.markdown(f"<h2 style='text-align:center'>{type_name}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; color:gray'>{type_desc}</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown(
        f"<div style='font-size:24px; font-weight:800;'>🎁 {region_label} 문화의날 추천 장소</div>",
        unsafe_allow_html=True
    )
    st.caption(f"👤 {user_info['gender']} · {user_info['age']} 선호도 기반 정렬 | 위로 올수록 선호도 높은 장소")
    st.markdown("<br>", unsafe_allow_html=True)

    if not df.empty:
        # 지역 필터링
        if sigungu != "전체":
            local = df[df['시군구'] == sigungu].copy()
        else:
            local = df[df['시도'] == sido].copy()

        used_places = set()
        used_categories = set()
        final = []

        # 1차: 메인 군집에서 2개 (카테고리별 1개씩)
        main_pool = local[local['Cluster_K3'].isin(main_clusters)]
        final += pick_by_category(main_pool, 2, used_places, used_categories, score_col)

        # 2차: 서브 군집에서 나머지 채우기
        sub_pool = local[local['Cluster_K3'].isin(sub_clusters)]
        final += pick_by_category(sub_pool, 4 - len(final), used_places, used_categories, score_col)

        # 3차: 부족하면 시/도 전체로 확장
        if len(final) < 4:
            sido_df = df[df['시도'] == sido].copy()
            main_sido = sido_df[sido_df['Cluster_K3'].isin(main_clusters)]
            sub_sido = sido_df[sido_df['Cluster_K3'].isin(sub_clusters)]
            final += pick_by_category(main_sido, 4 - len(final), used_places, used_categories, score_col)
            final += pick_by_category(sub_sido, 4 - len(final), used_places, used_categories, score_col)

        # 4차: 그래도 부족하면 카테고리 무시하고 보충
        if len(final) < 4:
            all_pool = local.copy()
            if score_col and score_col in all_pool.columns:
                all_pool = all_pool.sort_values(by=score_col, ascending=False, na_position='last')
            for _, row in all_pool.iterrows():
                if str(row.get('장소', '')) not in used_places:
                    used_places.add(str(row.get('장소', '')))
                    final.append(row.to_dict())
                if len(final) >= 4:
                    break

        mixed = len(final) > 0 and any(
            (sigungu != "전체" and p.get('시군구') != sigungu) or
            (sigungu == "전체" and p.get('시도') != sido)
            for p in final
        )

        if len(final) == 0:
            st.warning("해당 지역 장소가 부족합니다. 다른 지역을 선택해보세요!")
        else:
            if mixed:
                st.caption(f"📌 {region_label} 데이터가 부족해 {sido} 전체에서 보충했어요")

            for rank, place in enumerate(final, 1):
                emoji = cluster_emoji.get(place['Cluster_K3'], "🎭")
                with st.container():
                    st.markdown(
                        f"<div style='background:#f8f9fa; border-left:4px solid #4e8cff; "
                        f"border-radius:8px; padding:12px 16px; margin-bottom:8px;'>"
                        f"<span style='color:#4e8cff; font-size:14px; font-weight:600;'>✦ {rank}위</span><br>"
                        f"<span style='font-size:20px; font-weight:800;'>{emoji} {place['장소']}</span></div>",
                        unsafe_allow_html=True
                    )
                    st.caption(f"📍 {place['시도']} {place['시군구']} | {cluster_names.get(place['Cluster_K3'], '')}")

                    raw_혜택 = str(place['혜택'])
                    if 'http' in raw_혜택 or 'www' in raw_혜택:
                        혜택_text = f"• {raw_혜택.strip()}"
                    else:
                        혜택_lines = raw_혜택.split('/')
                        혜택_text = '<br>'.join([f"• {line.strip()}" for line in 혜택_lines if line.strip()])
                    st.markdown(f"🎁 **문화의날 혜택:**<br>{혜택_text}", unsafe_allow_html=True)

                    period = safe_get(place, '기간')
                    if period:
                        st.markdown(f"📅 **이용 기간:** {period}")

                    paid = safe_get(place, '유무료')
                    if paid:
                        st.markdown(f"💳 **유무료:** {paid}")

                    contact = safe_get(place, '연락처')
                    if contact:
                        st.markdown(f"📞 **연락처:** {contact}")

                    search_query = urllib.parse.quote(place['장소'])
                    naver_url = f"https://search.naver.com/search.naver?query={search_query}"
                    st.markdown(f"[🔍 {place['장소']} 정보 더 보기]({naver_url})")
                    st.divider()

    st.markdown("---")

    companions = get_companion_types(my_code, n=2)
    if companions:
        st.markdown("#### 🤝 같이 가면 좋을 유형")
        cols = st.columns(len(companions))
        for col, (overlap, code, name, desc) in zip(cols, companions):
            with col:
                if code in character_images:
                    st.image(character_images[code], width=180)
                st.markdown(f"**{name}**")
                st.caption(desc)

    st.markdown("---")
    if st.button("↻ 다시 테스트하기", use_container_width=True):
        st.session_state.step = 0
        st.session_state.answers = []
        st.rerun()

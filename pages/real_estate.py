import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database import get_connection, load_data, get_available_months, get_budgets
import plotly.graph_objects as go
from core.finance import calculate_fv as _fv, calculate_asset_fv as _afv, calculate_max_loan, opportunity_cost as _opp_cost
from core.real_estate import project_price
from components.charts import make_radar_chart, make_gap_chart
from components.formatters import format_korean

# Import 상수 
from config import (
    MONTHLY_INCOME, CURRENT_INVESTMENT, CURRENT_JEONSE_DEPOSIT,
    CURRENT_SAVINGS_DEPOSIT, MONTHLY_SAVING_TARGET, TARGET_EQUITY,
    TARGET_PRICE_LOW, TARGET_PRICE_HIGH, VARIABLE_BUDGET_LIMIT, 
    TARGET_DATE_YEAR, TARGET_DATE_MONTH, MORTGAGE_RATE, MORTGAGE_YEARS,
    DSR_LIMIT, AREA_M2, PYEONG
)

VARIABLE_BUDGET_LIMIT = 3_500_000  # 월 변동지출 한도 (주담대 가처분 계산용)

# ── 입지 스코어카드 데이터 ────────────────────────────────────
CANDIDATE_AREAS = {
    "성북구 길음뉴타운": {"교육": 85, "교통": 80, "생활편의": 75, "자산성장": 80, "price_2026": 8.0, "growth_rate": 0.04},
    "수지구":            {"교육": 95, "교통": 75, "생활편의": 70, "자산성장": 70, "price_2026": 8.5, "growth_rate": 0.03},
    "의정부 신일유토빌": {"교육": 40, "교통": 70, "생활편의": 65, "자산성장": 30, "price_2026": 4.5, "growth_rate": 0.01},
}
RADAR_COLS = ["교육", "교통", "생활편의", "자산성장"]

# ── 국토부 API 법정동 코드 ────────────────────────────────────
SIGUNGU_CODES = {
    "서울 성북구":    "11290",
    "서울 노원구":    "11350",
    "경기 구리시":    "41310",
    "경기 남양주시":  "41360",
    "경기 의정부시":  "41150",
    "경기 용인 수지": "41465",
}

# ── 후보 단지 딕셔너리 ────────────────────────────────────────
CANDIDATE_LIST = {
    "경기 의정부시":  {
        "신축": ["의정부역센트럴자이앤위브캐슬", "의정부 힐스테이트"],
        "구축": ["신일유토빌", "의정부 현대홈타운"]},
    "경기 구리시":    {
        "신축": ["e편한세상인창어반포레", "구리갈매 롯데캐슬"],
        "구축": ["구리우성한양", "구리 교문 현대"]},
    "서울 성북구":    {
        "신축": ["월곡 래미안 월곡", "꿈의숲 푸르지오", "두산위브"],
        "구축": ["길음뉴타운 래미안", "성북 SK뷰"]},
    "서울 노원구":    {
        "신축": ["노원 롯데캐슬", "상계 더샵"],
        "구축": ["상계주공", "상계 현대"]},
    "경기 남양주시":  {
        "신축": ["다산진건 푸르지오", "다산자이"],
        "구축": ["도농역 대림", "퇴계원 한화"]},
    "경기 용인 수지": {
        "신축": ["성복역 롯데캐슬", "수지 푸르지오"],
        "구축": ["풍덕천 현대", "수지 동아"]},
}

# ── 하드코딩 폴백 데이터 ─────────────────────────────────────
FALLBACK_DATA = [
    {"지역":"서울 성북구","단지명":"월곡 래미안 월곡","구분":"신축","최근거래가(만)":88000,"평균거래가(만)":87000,"전세가(만)":53000,"전세가율(%)":60,"갭(만)":35000,"건축년도":2020,"거래건수":4,"메모":"월곡역 역세권"},
    {"지역":"서울 성북구","단지명":"꿈의숲 푸르지오","구분":"신축","최근거래가(만)":85000,"평균거래가(만)":84000,"전세가(만)":51000,"전세가율(%)":61,"갭(만)":34000,"건축년도":2019,"거래건수":3,"메모":"4호선 인근"},
    {"지역":"서울 성북구","단지명":"두산위브","구분":"신축","최근거래가(만)":82000,"평균거래가(만)":81000,"전세가(만)":50000,"전세가율(%)":61,"갭(만)":32000,"건축년도":2018,"거래건수":2,"메모":""},
    {"지역":"서울 성북구","단지명":"길음뉴타운 래미안","구분":"구축","최근거래가(만)":79000,"평균거래가(만)":78000,"전세가(만)":49000,"전세가율(%)":62,"갭(만)":30000,"건축년도":2005,"거래건수":6,"메모":"4호선 길음역"},
    {"지역":"경기 구리시","단지명":"e편한세상인창어반포레","구분":"신축","최근거래가(만)":81000,"평균거래가(만)":80000,"전세가(만)":50000,"전세가율(%)":62,"갭(만)":31000,"건축년도":2022,"거래건수":5,"메모":"8호선 연장"},
    {"지역":"경기 구리시","단지명":"구리우성한양","구분":"구축","최근거래가(만)":63000,"평균거래가(만)":62000,"전세가(만)":42000,"전세가율(%)":67,"갭(만)":21000,"건축년도":1994,"거래건수":3,"메모":"저평가 역세권"},
    {"지역":"경기 남양주시","단지명":"다산진건 푸르지오","구분":"신축","최근거래가(만)":74000,"평균거래가(만)":73000,"전세가(만)":46000,"전세가율(%)":63,"갭(만)":28000,"건축년도":2020,"거래건수":7,"메모":"경춘선·GTX-B"},
    {"지역":"경기 의정부시","단지명":"의정부역센트럴자이앤위브캐슬","구분":"신축","최근거래가(만)":65000,"평균거래가(만)":64000,"전세가(만)":42000,"전세가율(%)":65,"갭(만)":23000,"건축년도":2023,"거래건수":8,"메모":"의정부역 도보"},
    {"지역":"경기 의정부시","단지명":"신일유토빌","구분":"구축","최근거래가(만)":48000,"평균거래가(만)":47000,"전세가(만)":33000,"전세가율(%)":70,"갭(만)":15000,"건축년도":2001,"거래건수":4,"메모":"호원2동 저평가"},
    {"지역":"경기 용인 수지","단지명":"성복역 롯데캐슬","구분":"신축","최근거래가(만)":85000,"평균거래가(만)":84000,"전세가(만)":54000,"전세가율(%)":64,"갭(만)":31000,"건축년도":2019,"거래건수":5,"메모":"신분당선·학군"},
]


# ── watch_list DB 헬퍼 ────────────────────────────────────────


def init_watch_list():
    """테이블 생성 + 시드 데이터 최초 1회 삽입. 앱 시작 시 자동 호출."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS watch_list (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            region       TEXT NOT NULL,
            complex_name TEXT NOT NULL,
            category     TEXT NOT NULL,
            is_active    INTEGER DEFAULT 1,
            memo         TEXT DEFAULT '',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(region, complex_name)
        )
    """)
    conn.commit()
    c.execute("SELECT COUNT(*) FROM watch_list")
    if c.fetchone()[0] == 0:
        seeds = [
            ("경기 의정부시",  "의정부역센트럴자이앤위브캐슬", "신축", "의정부역 도보"),
            ("경기 의정부시",  "신일유토빌",                   "구축", "호원2동 저평가"),
            ("경기 구리시",    "e편한세상인창어반포레",         "신축", "8호선 연장"),
            ("경기 구리시",    "구리우성한양",                  "구축", "역세권 저평가"),
            ("서울 성북구",    "월곡 래미안 월곡",              "신축", "월곡역"),
            ("서울 성북구",    "꿈의숲 푸르지오",               "신축", ""),
            ("서울 성북구",    "두산위브",                      "신축", ""),
            ("서울 성북구",    "길음뉴타운 래미안",             "구축", "4호선"),
            ("경기 남양주시",  "다산진건 푸르지오",             "신축", "GTX-B"),
            ("경기 용인 수지", "성복역 롯데캐슬",               "신축", "신분당선"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO watch_list (region,complex_name,category,memo) VALUES (?,?,?,?)",
            seeds,
        )
        conn.commit()
    conn.close()


def get_watch_list(active_only: bool = False) -> pd.DataFrame:
    conn = get_connection()
    try:
        q = "SELECT * FROM watch_list"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY region, category, complex_name"
        return pd.read_sql(q, conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()


def add_complex(region, name, category, memo="") -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO watch_list (region,complex_name,category,memo) VALUES (?,?,?,?)",
            (region, name, category, memo),
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def delete_complex(watch_id: int):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM watch_list WHERE id=?", (watch_id,))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def toggle_active(watch_id: int, value: int):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE watch_list SET is_active=? WHERE id=?", (value, watch_id))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


# ── 계산 헬퍼 ─────────────────────────────────────────────────

def months_until(year, month) -> int:
    now = datetime.now()
    return max((year - now.year) * 12 + (month - now.month), 1)



def calc_savings_speed(manual_saving: int = None) -> dict:
    """
    월 저축액 계산. 세 가지 모드:
      1. manual_saving 지정 시 → 해당 값 그대로 사용 (직접 입력)
      2. manual_saving = -1    → budgets 테이블 기반 계획 지출로 역산
      3. manual_saving = None  → DB expenses 최근 3개월 실지출 역산 (기존 방식)
    """
    fallback_used = False

    if manual_saving is not None and manual_saving >= 0:
        # 모드 1: 직접 입력
        avg = manual_saving

    elif manual_saving == -1:
        # 모드 2: budgets 테이블 기반
        b_df = get_budgets()
        if not b_df.empty:
            planned_expense = int(b_df["amount"].sum())
            avg = MONTHLY_INCOME - planned_expense
        else:
            # budgets 미설정 시 폴백
            avg = MONTHLY_SAVING_TARGET
            fallback_used = True

    else:
        # 모드 3: DB 실지출 역산 (기존)
        months = get_available_months()[:3]
        savings = []
        for m in months:
            df = load_data(m)
            if not df.empty:
                savings.append(MONTHLY_INCOME - int(df["amount"].sum()))
        if savings:
            avg = int(sum(savings) / len(savings))
        else:
            avg = MONTHLY_SAVING_TARGET
            fallback_used = True

    months_left     = months_until(TARGET_DATE_YEAR, TARGET_DATE_MONTH)
    expected_accum  = avg * months_left
    expected_equity = (CURRENT_INVESTMENT + CURRENT_JEONSE_DEPOSIT
                       + CURRENT_SAVINGS_DEPOSIT + expected_accum)
    prob = min(expected_equity / TARGET_EQUITY * 100, 100.0)
    return dict(avg_saving=avg, months_left=months_left,
                expected_accum=expected_accum, expected_equity=expected_equity,
                prob=prob, fallback_used=fallback_used)


def calc_mortgage(price, equity, rate, years) -> dict:
    """원리금균등 주담대 계산."""
    loan = price - equity
    mr = rate / 12
    n = years * 12
    monthly = loan * mr / (1 - (1 + mr) ** (-n)) if mr > 0 else loan / n
    total_interest = monthly * n - loan
    ltv = loan / price
    dsr = (monthly * 12) / MONTHLY_INCOME
    disposable = MONTHLY_INCOME - monthly - VARIABLE_BUDGET_LIMIT
    return dict(loan=loan, monthly=monthly, total_interest=total_interest,
                ltv=ltv, dsr=dsr, disposable=disposable, n=n)


# ── 실시간 API 함수 ───────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_molit_trade(sigungu_code: str, year_month: str) -> pd.DataFrame:
    """국토부 아파트 매매 실거래가 API."""
    api_key = st.secrets.get("MOLIT_API_KEY", "")
    if not api_key:
        return pd.DataFrame()
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    try:
        res = requests.get(url, params={
            "serviceKey": api_key, "LAWD_CD": sigungu_code,
            "DEAL_YMD": year_month, "pageNo": 1, "numOfRows": 100,
        }, timeout=10)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        if not items:
            return pd.DataFrame()
        rows = []
        for item in items:
            def g(tag): return (item.findtext(tag) or "").strip()
            rows.append({
                "아파트":   g("아파트"),
                "법정동":   g("법정동"),
                "전용면적": float(g("전용면적") or 0),
                "거래금액": int(g("거래금액").replace(",", "") or 0),
                "건축년도": g("건축년도"),
                "계약년월": year_month,
            })
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_molit_rent(sigungu_code: str, year_month: str) -> pd.DataFrame:
    """국토부 아파트 전월세 API (전세만 필터)."""
    api_key = st.secrets.get("MOLIT_API_KEY", "")
    if not api_key:
        return pd.DataFrame()
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
    try:
        res = requests.get(url, params={
            "serviceKey": api_key, "LAWD_CD": sigungu_code,
            "DEAL_YMD": year_month, "pageNo": 1, "numOfRows": 100,
        }, timeout=10)
        root = ET.fromstring(res.content)
        rows = []
        for item in root.findall(".//item"):
            def g(tag): return (item.findtext(tag) or "").strip()
            wolse = int(g("월세금액").replace(",", "") or 0)
            if wolse == 0:
                rows.append({
                    "아파트":   g("아파트"),
                    "보증금액": int(g("보증금액").replace(",", "") or 0),
                })
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()


# ── 단지 선정 엔진 ────────────────────────────────────────────

def select_complex_data(
    trade_df: pd.DataFrame,
    rent_df: pd.DataFrame,
    region: str,
    area_min: float = 75.0,
    area_max: float = 95.0,
) -> pd.DataFrame:
    """watch_list(active_only=True)의 해당 region 단지를 trade_df에서 매칭·집계."""
    wl = get_watch_list(active_only=True)
    wl = wl[wl["region"] == region]
    if wl.empty or trade_df.empty:
        return pd.DataFrame()

    results = []
    for _, row in wl.iterrows():
        keyword = row["complex_name"].replace(" ", "")
        mask_t = trade_df["아파트"].str.replace(" ", "", regex=False)\
                                   .str.contains(keyword, case=False, na=False)
        mask_a = trade_df["전용면적"].between(area_min, area_max)
        matched = trade_df[mask_t & mask_a]

        if matched.empty:
            st.caption(f"⚠️ '{row['complex_name']}': 해당 기간 실거래 없음 (면적 {area_min}~{area_max}㎡)")
            continue

        recent_price = int(matched.sort_values("계약년월", ascending=False).iloc[0]["거래금액"])
        avg_price    = int(matched["거래금액"].mean())
        count        = len(matched)
        year_built   = matched["건축년도"].mode().iloc[0] if not matched["건축년도"].mode().empty else "-"
        area_val     = round(matched["전용면적"].median(), 1)

        jeonse_avg = None
        if not rent_df.empty:
            mask_r = rent_df["아파트"].str.replace(" ", "", regex=False)\
                                      .str.contains(keyword, case=False, na=False)
            matched_r = rent_df[mask_r]
            if not matched_r.empty:
                jeonse_avg = int(matched_r["보증금액"].mean())

        jeonse_rate = round(jeonse_avg / recent_price * 100, 1) if jeonse_avg else None
        gap         = recent_price - jeonse_avg if jeonse_avg else None

        results.append({
            "지역":          region,
            "단지명":        row["complex_name"],
            "구분":          row["category"],
            "전용㎡":        area_val,
            "최근거래가(만)": recent_price,
            "평균거래가(만)": avg_price,
            "전세가(만)":    jeonse_avg,
            "전세가율(%)":   jeonse_rate,
            "갭(만)":        gap,
            "건축년도":      year_built,
            "거래건수":      count,
            "메모":          row.get("memo", ""),
        })
    return pd.DataFrame(results)


def build_region_table(months_back: int = 3) -> pd.DataFrame:
    """is_active=1 단지의 region 집합만 API 호출."""
    active_df = get_watch_list(active_only=True)
    if active_df.empty:
        return pd.DataFrame()

    now = datetime.now()
    ym_list = [
        (now - relativedelta(months=i)).strftime("%Y%m")
        for i in range(months_back)
    ]

    active_regions = sorted(active_df["region"].unique())
    all_results = []

    for region in active_regions:
        code = SIGUNGU_CODES.get(region)
        if not code:
            st.warning(f"⚠️ '{region}': SIGUNGU_CODES에 코드 없음. 건너뜀.")
            continue
        trade_frames, rent_frames = [], []
        for ym in ym_list:
            t = fetch_molit_trade(code, ym)
            r = fetch_molit_rent(code, ym)
            if not t.empty: trade_frames.append(t)
            if not r.empty: rent_frames.append(r)

        trade_df = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
        rent_df  = pd.concat(rent_frames,  ignore_index=True) if rent_frames  else pd.DataFrame()

        region_result = select_complex_data(trade_df, rent_df, region)
        if not region_result.empty:
            all_results.append(region_result)

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()


# ── 페이지 설정 ───────────────────────────────────────────────

st.set_page_config(page_title="부동산 매수 전략", page_icon="🏠", layout="wide")
init_watch_list()


# ── 사이드바 ──────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ 시뮬레이션 설정")
    sim_equity  = st.slider("자기자본(억)", 2.0, 6.0, 5.0, 0.5,
                             key="sim_equity") * 1e8
    sim_price   = st.slider("매수가(억)",   5.0, 15.0, 9.0, 0.5,
                             key="sim_price") * 1e8
    sim_rate    = st.slider("금리(%)",      2.0, 8.0, 4.0, 0.5,
                             key="sim_rate") / 100
    sim_years   = st.selectbox("대출기간", [5, 10, 20, 25, 30, 40], index=2,
                                key="sim_years")
    excess_amt  = st.number_input("이번 달 초과 지출액(원)",
                                   value=500_000, step=10_000,
                                   key="excess_amount")

    st.divider()
    st.markdown("### 💰 월 저축액 계산 방식")

    # saving_mode = st.radio(
    #     "계산 기준",
    #     ["DB 실지출 역산 (최근 3개월)", "예산 기반 (budgets 테이블)", "직접 입력"],
    #     index=0,
    #     key="saving_mode",
    #     help=(
    #         "DB 역산: 소득 - 최근 3개월 평균 실지출\n"
    #         "예산 기반: 소득 - 설정한 월 총 예산\n"
    #         "직접 입력: 실제 저축 중인 금액 수동 입력"
    #     ),
    # )
    manual_saving_input = st.number_input(
        "월 저축액 직접 입력 (원)",
        min_value=0,
        max_value=MONTHLY_INCOME,
        value=MONTHLY_SAVING_TARGET,
        step=100_000,
        key="manual_saving",
    )
    _saving_arg = manual_saving_input

    # if saving_mode == "직접 입력":
    #     manual_saving_input = st.number_input(
    #         "월 저축액 직접 입력 (원)",
    #         min_value=0,
    #         max_value=MONTHLY_INCOME,
    #         value=MONTHLY_SAVING_TARGET,
    #         step=100_000,
    #         key="manual_saving",
    #     )
    #     _saving_arg = manual_saving_input
    # elif saving_mode == "예산 기반 (budgets 테이블)":
    #     _b_df = get_budgets()
    #     _planned = int(_b_df["amount"].sum()) if not _b_df.empty else None
    #     if _planned:
    #         st.caption(
    #             f"📋 설정 예산 합계: **{_planned:,}원**  \n"
    #             f"→ 예상 저축: **{MONTHLY_INCOME - _planned:,}원**"
    #         )
    #     else:
    #         st.warning("⚠️ 예산이 설정되지 않았습니다. budget 페이지에서 먼저 설정하세요.")
    #     _saving_arg = -1   # calc_savings_speed에서 budgets 모드 트리거
    # else:
    #     _saving_arg = None  # DB 역산 모드 (기존)

    st.divider()
    st.markdown("### 🏢 관심 단지 필터")

    all_wl = get_watch_list(active_only=False)
    if all_wl.empty:
        st.caption("관심 단지 없음. Tab3에서 추가하세요.")
    else:
        toggled = False
        for region in sorted(all_wl["region"].unique()):
            st.caption(f"📍 {region}")
            for _, row in all_wl[all_wl["region"] == region]\
                              .sort_values("category").iterrows():
                icon  = "🆕" if row["category"] == "신축" else "🏚️"
                checked = st.checkbox(
                    f"{icon} {row['complex_name']}",
                    value=bool(row["is_active"]),
                    key=f"sb_{row['id']}",
                )
                # ★ DB만 바꾸고 toggled 플래그 세팅 — rerun은 루프 완료 후 1회
                if checked != bool(row["is_active"]):
                    toggle_active(row["id"], int(checked))
                    toggled = True
        active_n = int(all_wl["is_active"].sum())
        st.caption(f"✅ {active_n}/{len(all_wl)}개 활성")
        if toggled:
            st.rerun()  # ★ 루프 밖에서 1회만 rerun → 중복 rerun 방지


# ── 메인 ──────────────────────────────────────────────────────

st.title("🏠 부동산 매수 전략")
st.caption("2029년 2월 서울·경기 상급지 84㎡ 매수 목표 | 자기자본 5억 달성 로드맵")

# ── 실거래 데이터 로드 (Tab3 진입 시점에만 실행) ─────────────
_api_key = st.secrets.get("MOLIT_API_KEY", "")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 매수 가능성 진단",
    "💥 기회비용 시각화",
    "🗺️ 지역별 단지 추천",
    "🏦 주담대 시뮬레이터",
    "🏫 입지 스코어카드",
    "📉 자산 격차 트래커",
])


# ── Tab 1: 매수 가능성 진단 ───────────────────────────────────

with tab1:
    sp = calc_savings_speed(manual_saving=_saving_arg)

    # 계산 방식 출처 표시
    mode_labels = {
        None: "📊 DB 실지출 역산 (최근 3개월 평균)",
        -1:   "📋 예산 기반 (budgets 테이블 계획 지출)",
    }
    if _saving_arg in mode_labels:
        mode_label = mode_labels[_saving_arg]
    else:
        mode_label = f"✏️ 직접 입력 ({_saving_arg:,}원)"
        st.caption(f"저축액 계산 기준: **{mode_label}**")

    if sp["fallback_used"]:
        st.info("📭 데이터 없음 — 목표 저축액(325만)으로 대체했습니다. 사이드바에서 계산 방식을 변경해 주세요.")

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 월 평균 저축속도",
                  f"{sp['avg_saving']:,}원",
                  delta=f"{sp['avg_saving']-MONTHLY_SAVING_TARGET:+,}원 (목표 대비)",
                  delta_color="normal")
        c2.metric("🏦 예상 자기자본 (2029.02)",
                  f"{sp['expected_equity']/1e8:.2f}억",
                  delta=f"부족액 {max(TARGET_EQUITY-sp['expected_equity'],0)/1e4:.0f}만")
        prob_delta_color = "inverse" if sp["prob"] < 80 else "normal"
        c3.metric("🎯 목표 달성 확률",
                  f"{sp['prob']:.1f}%",
                  delta_color=prob_delta_color)

    st.progress(min(sp["prob"] / 100, 1.0))

    if sp["prob"] < 80:
        st.warning("🚨 현재 저축 속도로는 2029년 2월까지 목표 자기자본 5억 달성이 어렵습니다.")
    elif sp["prob"] >= 100:
        st.success("✅ 현재 속도를 유지하면 목표 달성 가능합니다!")

    st.markdown("#### 📊 저축 시나리오 비교")
    scenarios = []
    for label, saving in [
        ("현재 속도", sp["avg_saving"]),
        ("목표 속도 (325만)", MONTHLY_SAVING_TARGET),
        ("절약 +35만", sp["avg_saving"] + 350_000),
    ]:
        accum  = saving * sp["months_left"]
        equity = CURRENT_INVESTMENT + CURRENT_JEONSE_DEPOSIT + \
                 CURRENT_SAVINGS_DEPOSIT + accum
        prob   = min(equity / TARGET_EQUITY * 100, 100.0)
        short  = max(TARGET_EQUITY - equity, 0)
        scenarios.append({"시나리오": label,
                           "월 저축": f"{saving:,}원",
                           "예상 자기자본": f"{equity/1e8:.2f}억",
                           "달성 확률": f"{prob:.1f}%",
                           "부족액": f"{short/1e4:.0f}만원"})
    st.dataframe(pd.DataFrame(scenarios), use_container_width=True, hide_index=True)

    # ── 관심 단지 매수 가능성 ──────────────────────────────────
    # ★ Tab1은 폴백 데이터 기준 (API 호출 없음 — Tab3에서 실시간 조회)
    _active_wl    = get_watch_list(active_only=True)
    _active_names = set(_active_wl["complex_name"].tolist()) if not _active_wl.empty else set()
    _fallback_all = pd.DataFrame(FALLBACK_DATA)
    result_df = (
        _fallback_all[_fallback_all["단지명"].isin(_active_names)].copy()
        if _active_names else pd.DataFrame()
    )

    st.markdown("#### 🏢 관심 단지 매수 가능성")
    st.caption("💡 달성 확률 = 예상 자기자본 ÷ 목표 5억 × 100")
    if result_df.empty or "최근거래가(만)" not in result_df.columns:
        st.info("⚙️ 사이드바에서 단지를 활성화하면 매수 가능성 분석이 표시됩니다.")
    else:
        eq_now   = CURRENT_INVESTMENT + CURRENT_JEONSE_DEPOSIT + CURRENT_SAVINGS_DEPOSIT   # 현재 자기자본
        eq_2029  = sp["expected_equity"]        # 2029.02 예상 자기자본

        # DSR 40% 기준 최대 대출원금 (MORTGAGE_RATE, MORTGAGE_YEARS 상수 사용)
        max_loan_dsr = int(calculate_max_loan(MONTHLY_INCOME, MORTGAGE_RATE, MORTGAGE_YEARS))

        # 지역별 연 상승률 매핑 (CANDIDATE_AREAS 기반)
        REGION_GROWTH = {
            "서울 성북구":    0.04,
            "경기 용인 수지": 0.03,
            "경기 의정부시":  0.01,
            "경기 구리시":    0.03,
            "경기 남양주시":  0.03,
            "서울 노원구":    0.03,
        }

        diag_rows = []
        for _, r in result_df.iterrows():
            price_now_won  = r["최근거래가(만)"] * 10_000
            growth         = REGION_GROWTH.get(r["지역"], 0.03)
            price_2029_won = price_now_won * ((1 + growth) ** 3)

            # 현재 매수: 현 자기자본 >= 단지현재가 × 30% (LTV 70% 가정)            
            can_now = (eq_now >= price_now_won * 0.3) and ((eq_now + max_loan_dsr) >= price_now_won)

            
            # 2029 매수: 예상 자기자본 + DSR 최대대출 >= 2029 예상 단지가
            can_2029 = (eq_2029 + max_loan_dsr) >= price_2029_won

            short_now = max(
                price_now_won * 0.3 - eq_now,              # LTV 부족분
                price_now_won - eq_now - max_loan_dsr,      # 총액 부족분
                0
            ) / 10_000
            short_2029 = max(price_2029_won - eq_2029 - max_loan_dsr, 0) / 10_000

            diag_rows.append({
                "지역":              r["지역"],
                "단지명":            r["단지명"],
                "구분":              r["구분"],
                "현재가(만)":        r["최근거래가(만)"],
                "2029예상가(만)":    int(price_2029_won / 10_000),
                "현재 매수":         "✅ 가능" if can_now  else "❌ 부족",
                "2029.02 매수":      "✅ 가능" if can_2029 else "❌ 부족",
                "현재 부족액(만)":   f"{short_now:.0f}"  if not can_now  else "-",
                "2029 부족액(만)":   f"{short_2029:.0f}" if not can_2029 else "-",
            })

        diag_df = pd.DataFrame(diag_rows).sort_values(["2029.02 매수", "현재가(만)"])
        st.dataframe(
            diag_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "현재가(만)":     st.column_config.NumberColumn(format="%d만"),
                "2029예상가(만)": st.column_config.NumberColumn(format="%d만"),
                "현재 매수":      st.column_config.TextColumn(width="small"),
                "2029.02 매수":   st.column_config.TextColumn(width="small"),
            },
        )
        n_ok = (diag_df["2029.02 매수"] == "✅ 가능").sum()
        st.caption(
            f"📊 현재 자기자본 {eq_now/1e8:.2f}억 · 2029.02 예상 {eq_2029/1e8:.2f}억 · DSR 최대대출 {max_loan_dsr/1e8:.2f}억 기준 | "
            f"2029년까지 매수 가능 단지 {n_ok}/{len(diag_df)}개"
        )
        with st.expander("📖 판단 기준 설명"):
            st.markdown(
                f"""
**현재 매수 가능** — 현 보유 자기자본({eq_now/1e8:.2f}억)이 단지 현재가의 30% 이상인 경우
&nbsp;&nbsp;&nbsp;&nbsp;→ LTV 70% 가정: 필요 자기자본 = 단지가 × 30%

**2029 매수 가능** — 예상 자기자본({eq_2029/1e8:.2f}억) + DSR 최대대출({max_loan_dsr/1e8:.2f}억)이 2029년 예상 단지가 이상인 경우
&nbsp;&nbsp;&nbsp;&nbsp;→ 2029 예상가 = 현재가 × (1 + 지역 연 상승률)³
&nbsp;&nbsp;&nbsp;&nbsp;→ DSR 최대대출: 월소득 {MONTHLY_INCOME:,}원 기준 DSR 40%, 금리 {MORTGAGE_RATE*100:.1f}%, {MORTGAGE_YEARS}년

**달성 확률 < 100% + 현재 매수 가능** → 정상: 자기자본이 LTV 30%는 충족하지만 목표 5억엔 미달인 경우
                """
            )


# ── Tab 2: 기회비용 시각화 ────────────────────────────────────

with tab2:
    excess = int(excess_amt)
    ml = months_until(TARGET_DATE_YEAR, TARGET_DATE_MONTH)
    fv = _afv(excess, 0.06, ml)
    mortgage_monthly_interest = (TARGET_PRICE_HIGH - TARGET_EQUITY) * MORTGAGE_RATE / 12
    interest_months = fv / mortgage_monthly_interest if mortgage_monthly_interest > 0 else 0
    price_per_pyeong = TARGET_PRICE_HIGH / PYEONG
    lost_pyeong = fv / price_per_pyeong
    fv_annual = _afv(excess * 12, 0.06, ml)

    st.error(
        f"🚨 이번 달 **{excess:,}원** 초과 → "
        f"{ml}개월 복리(연 6%) 후 **{fv:,.0f}원** 증발"
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("💸 사라진 미래 자산", f"{fv:,.0f}원",
                  delta=f"+{fv-excess:,.0f}원 복리 증식분", delta_color="inverse")
        c2.metric("🏦 주담대 이자 환산", f"{interest_months:.1f}개월치",
                  delta=f"월 이자 {mortgage_monthly_interest:,.0f}원 기준",
                  delta_color="inverse")
        c3.metric("📐 아파트 손실 면적", f"{lost_pyeong:.3f}평",
                  delta=f"평당 {price_per_pyeong:,.0f}원 기준",
                  delta_color="inverse")

    st.warning(
        f"💬 매달 반복 시 — 연간 {excess*12:,}원 초과 → "
        f"2029년까지 **{fv_annual:,.0f}원** 손실"
    )

    st.markdown("#### 🧮 절약 시뮬레이터")
    if excess <= 10_000:
        st.info("초과 지출액이 없거나 너무 적어 절약 시뮬레이터를 표시할 수 없습니다.")
    else:
        slider_max = max(min(excess, 1_000_000), 20_000)  # 최소 2스텝 확보
        save_target = st.slider("매달 이만큼 줄이면...", 10_000,
                                 slider_max,
                                 min(excess // 2, slider_max), 10_000,
                                 format="%d원")
        sim_fv = _afv(save_target, 0.06, ml)
        sc1, sc2 = st.columns(2)
        sc1.metric(f"2029년 2월 (+{ml}개월)", f"{sim_fv:,.0f}원",
                   f"절약 {save_target:,}원의 미래가치")
        ytr = TARGET_DATE_YEAR + 22 - datetime.now().year
        sc2.metric(f"은퇴 시점 (+{ytr}년)",
                   f"{_afv(save_target, 0.06, ytr*12):,.0f}원",
                   f"연 6% 복리")


# ── Tab 3: 지역별 단지 추천 ──────────────────────────────────

with tab3:

    with st.expander("⚙️ 관심 단지 관리", expanded=False):

        st.markdown("**① 추천 후보에서 선택**")
        c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
        sel_r = c1.selectbox("지역", list(CANDIDATE_LIST.keys()), key="c_region")
        sel_c = c2.selectbox("구분", ["신축", "구축"], key="c_cat")
        sel_n = c3.selectbox("단지", CANDIDATE_LIST[sel_r][sel_c], key="c_name")
        c4.write(""); c4.write("")
        if c4.button("➕ 추가", key="c_add", use_container_width=True):
            if add_complex(sel_r, sel_n, sel_c):
                st.toast(f"✅ '{sel_n}' 추가됨"); st.rerun()
            else:
                st.warning("⚠️ 이미 목록에 있습니다.")

        st.divider()

        st.markdown("**② 직접 입력** (단지명 일부만 입력해도 API contains 매칭)")
        d1, d2, d3, d4 = st.columns([2, 2, 1, 1])
        d_r = d1.selectbox("지역 ", list(SIGUNGU_CODES.keys()), key="d_region")
        d_n = d2.text_input("단지명", key="d_name", placeholder="예: 자이앤위브")
        d_c = d3.selectbox("구분 ", ["신축", "구축"], key="d_cat")
        d_m = d4.text_input("메모", key="d_memo", placeholder="선택사항")
        if st.button("➕ 직접 추가", key="d_add", use_container_width=True):
            if not d_n.strip():
                st.error("단지명을 입력하세요.")
            elif add_complex(d_r, d_n.strip(), d_c, d_m.strip()):
                st.toast(f"✅ '{d_n}' 추가됨"); st.rerun()
            else:
                st.warning("⚠️ 동일 지역+단지명이 이미 존재합니다.")

        st.divider()

        st.markdown("**📋 현재 관심 단지 목록**")
        cur_df = get_watch_list(active_only=False)\
                     .sort_values(["region", "category", "complex_name"])
        if cur_df.empty:
            st.info("관심 단지가 없습니다. 위에서 추가해 주세요.")
        else:
            st.dataframe(
                cur_df[["region", "complex_name", "category", "memo"]].rename(columns={
                    "region": "지역", "complex_name": "단지명",
                    "category": "구분", "memo": "메모"}),
                use_container_width=True, hide_index=True,
            )
            col_s, col_d = st.columns([4, 1])
            del_id = col_s.selectbox(
                "삭제할 단지",
                options=cur_df["id"].tolist(),
                format_func=lambda i: (
                    cur_df.loc[cur_df["id"] == i, "complex_name"].values[0]
                    + " · " + cur_df.loc[cur_df["id"] == i, "region"].values[0]
                ),
                key="del_select",
            )
            col_d.write(""); col_d.write("")
            if col_d.button("🗑️ 삭제", key="del_btn"):
                delete_complex(del_id)
                st.toast("🗑️ 삭제됐습니다."); st.rerun()

    # ★ result_df를 Tab3 내부에서 계산 — 스피너가 Tab3 안에서만 표시됨
    if not _api_key:
        _active_wl2   = get_watch_list(active_only=True)
        _active_names2 = set(_active_wl2["complex_name"].tolist()) if not _active_wl2.empty else set()
        _fallback_all2 = pd.DataFrame(FALLBACK_DATA)
        result_df = (
            _fallback_all2[_fallback_all2["단지명"].isin(_active_names2)].copy()
            if _active_names2 else pd.DataFrame()
        )
    else:
        with st.spinner("🔍 국토부 실거래가 API 조회 중... (최대 약 20초)"):
            result_df = build_region_table(months_back=3)

    # result_df는 탭 밖에서 공통 계산됨
    if not _api_key:
        st.warning(
            "⚙️ 실시간 데이터를 사용하려면 `.streamlit/secrets.toml`에 "
            "`MOLIT_API_KEY`를 입력하세요. "
            "[data.go.kr](https://www.data.go.kr)에서 무료 발급."
        )
        if result_df.empty:
            st.info("⚙️ 사이드바에서 단지를 활성화하면 데이터가 표시됩니다.")
        else:
            st.caption("📌 현재 2025~2026년 초 국토부 실거래 기반 하드코딩 데이터 표시 중 (활성 단지만)")
    else:
        if result_df.empty:
            st.info("⚙️ 사이드바에서 단지를 활성화하거나 위에서 단지를 추가해 주세요.")

    if not result_df.empty:
        equity_input = CURRENT_INVESTMENT + CURRENT_JEONSE_DEPOSIT + CURRENT_SAVINGS_DEPOSIT

        for region in sorted(result_df["지역"].unique()):
            st.markdown(f"### 📍 {region}")
            region_df = result_df[result_df["지역"] == region]

            for cat, icon in [("신축", "🆕"), ("구축", "🏚️")]:
                cat_df = region_df[region_df["구분"] == cat].copy()
                if cat_df.empty:
                    continue

                st.markdown(f"**{icon} {cat}**")

                # price_now_won 기준 LTV 30% 자기자본 필요
                cat_df["매수가능"] = cat_df.apply(
                    lambda row: "✅ 가능" if (
                        row["최근거래가(만)"] is not None
                        and equity_input >= row["최근거래가(만)"] * 10_000 * 0.3
                    ) else "❌ 자기자본 부족",
                    axis=1
                )

                display_cols = ["단지명", "전용㎡", "최근거래가(만)", "평균거래가(만)",
                                "전세가(만)", "전세가율(%)", "갭(만)", "거래건수", "매수가능", "메모"]
                display_cols = [c for c in display_cols if c in cat_df.columns]

                st.dataframe(
                    cat_df[display_cols],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "최근거래가(만)": st.column_config.NumberColumn(format="%d만"),
                        "평균거래가(만)": st.column_config.NumberColumn(format="%d만"),
                        "전세가(만)":     st.column_config.NumberColumn(format="%d만"),
                        "갭(만)":         st.column_config.NumberColumn(format="%d만"),
                        "전세가율(%)":    st.column_config.ProgressColumn(
                                              min_value=0, max_value=100, format="%.0f%%"),
                    },
                )

            if "의정부" in region:
                st.info("🏠 현 거주지 인근 — 이사 비용·생활 반경 유지 시 갭 최소 전략")

        st.caption(f"📊 현재 자기자본 {equity_input/1e8:.2f}억 기준 매수가능 여부 | 2029 목표: {float(sim_equity)/1e8:.2f}억")


# ── Tab 4: 주담대 시뮬레이터 ─────────────────────────────────

with tab4:
    mg = calc_mortgage(sim_price, sim_equity, sim_rate, sim_years)

    if mg["ltv"] > 0.7:
        st.error(f"❌ LTV {mg['ltv']*100:.1f}% — 70% 초과, 대출 불가")
    elif mg["dsr"] > DSR_LIMIT:
        st.error(f"❌ DSR {mg['dsr']*100:.1f}% — 40% 초과, 대출 제한")
    else:
        st.success(f"✅ LTV {mg['ltv']*100:.1f}% · DSR {mg['dsr']*100:.1f}% — 대출 가능")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💳 대출액",       f"{mg['loan']/1e8:.2f}억")
        c2.metric("📅 월 상환액",    f"{mg['monthly']:,.0f}원")
        c3.metric("💸 총 이자",      f"{mg['total_interest']/1e8:.2f}억")
        c4.metric("🧾 매수 후 월 가처분",
                  f"{mg['disposable']:,.0f}원",
                  delta_color="inverse" if mg["disposable"] < 500_000 else "normal")

    if mg["disposable"] < 500_000:
        st.error("⚠️ 상환 후 월 가처분소득이 위험 수준입니다. 매수가 또는 대출기간을 조정하세요.")
    elif mg["disposable"] < 1_000_000:
        st.warning("⚠️ 가처분소득 여유가 적습니다. 비상금 확보 계획을 세우세요.")

    st.markdown("#### 📋 초반 5년 상환 스케줄")
    mr = sim_rate / 12
    balance = mg["loan"]
    monthly = mg["monthly"]
    schedule = []
    for yr in range(1, 6):
        annual_interest  = 0
        annual_principal = 0
        for _ in range(12):
            interest   = balance * mr
            principal  = monthly - interest
            annual_interest  += interest
            annual_principal += principal
            balance -= principal
        schedule.append({
            "년차": f"{yr}년차",
            "연간 원금상환": f"{annual_principal:,.0f}원",
            "연간 이자":     f"{annual_interest:,.0f}원",
            "연말 잔액":     f"{max(balance, 0):,.0f}원",
        })
    st.dataframe(pd.DataFrame(schedule), use_container_width=True, hide_index=True)


# ── Tab 5: 입지 스코어카드 ────────────────────────────────────

with tab5:
    st.subheader("🏫 입지 스코어카드 — 후보 지역 비교")

    # 가중치 슬라이더
    edu_weight = st.slider("교육 가중치 (%)", min_value=0, max_value=100, value=50, step=5)
    remaining_w = (100 - edu_weight) / 3
    weights = {
        "교육":    edu_weight / 100,
        "교통":    remaining_w / 100,
        "생활편의": remaining_w / 100,
        "자산성장": remaining_w / 100,
    }
    st.caption(f"교통 · 생활편의 · 자산성장 각 {remaining_w:.1f}% 자동 배분")

    # 가중 합산 점수 계산
    rows = []
    for area, data in CANDIDATE_AREAS.items():
        score = sum(data[col] * weights[col] for col in RADAR_COLS)
        price_2029 = project_price(data["price_2026"], data["growth_rate"])
        rows.append({
            "지역":        area,
            "교육":        data["교육"],
            "교통":        data["교통"],
            "생활편의":    data["생활편의"],
            "자산성장":    data["자산성장"],
            "종합점수":    round(score, 1),
            "price_2026":  data["price_2026"],
            "growth_rate": data["growth_rate"],
            "2029 예상가(억)": round(price_2029, 2),
        })

    score_df = pd.DataFrame(rows).sort_values("종합점수", ascending=False).reset_index(drop=True)
    score_df.index += 1  # 1위부터 표시

    # 순위 테이블
    display_df = score_df[["지역", "교육", "교통", "생활편의", "자산성장", "종합점수", "2029 예상가(억)"]].copy()
    st.dataframe(display_df, use_container_width=True)

    # 레이더 차트
    st.markdown("#### 지역별 입지 지표 비교")
    fig_radar = make_radar_chart(score_df, RADAR_COLS)
    st.plotly_chart(fig_radar, use_container_width=True)

    # 2029 예상가 metric
    st.markdown("#### 2029년 예상 매매가 (2026 기준 연 복리)")
    m_cols = st.columns(len(CANDIDATE_AREAS))
    for i, (_, row) in enumerate(score_df.iterrows()):
        delta_pct = row["growth_rate"] * 3 * 100
        m_cols[i].metric(
            row["지역"],
            f"{row['2029 예상가(억)']:.2f}억",
            delta=f"+{delta_pct:.0f}% ({row['growth_rate']*100:.0f}%/yr)",
        )


# ── Tab 6: 자산 격차 트래커 ──────────────────────────────────

with tab6:
    st.subheader("📉 자산 격차 트래커 — 상급지 진입 가능성")

    # ── 연도별 데이터 생성 ────────────────────────────────────
    _GAP_YEARS     = list(range(2026, 2033))
    _UI_PRICE_0    = 4.5   # 의정부 신일유토빌 2026 기준가 (억)
    _UI_GROWTH     = 0.01
    _SB_PRICE_0    = 8.0   # 성북구 길음뉴타운 2026 기준가 (억)
    _SB_GROWTH     = 0.04
    _EQUITY_PMT    = 3_250_000   # 월 저축 (기본값)
    _EQUITY_PV     = 50_000_000  # 현재 투자자산
    _EQUITY_RATE   = 0.03        # 연 수익률
    _EQUITY_FIXED  = 25_000_000 + 260_000_000  # 청약 + 전세보증금 회수


    gap_rows = []
    for yr in _GAP_YEARS:
        elapsed = yr - 2026
        ui_price = _UI_PRICE_0 * (1 + _UI_GROWTH) ** elapsed
        sb_price = _SB_PRICE_0 * (1 + _SB_GROWTH) ** elapsed
        n_months_gap = max(0, (yr - 2026) * 12)
        equity = (
            _fv(_EQUITY_PMT, _EQUITY_RATE, n_months_gap)
            + _afv(_EQUITY_PV, _EQUITY_RATE, n_months_gap)
            + _EQUITY_FIXED
        ) / 1e8
        gap_rows.append({
            "연도":              yr,
            "의정부 신일유토빌": round(ui_price, 2),
            "성북구 길음뉴타운": round(sb_price, 2),
            "내 자기자본":       round(equity, 2),
            "Gap(성북-의정부)":  round(sb_price - ui_price, 2),
        })

    gap_df = pd.DataFrame(gap_rows)

    row_2029 = gap_df[gap_df["연도"] == 2029].iloc[0] if not gap_df[gap_df["연도"] == 2029].empty else None
    gap_2029 = row_2029["Gap(성북-의정부)"] if row_2029 is not None else 0.0

    # 경고 로직도 방어 처리
    if row_2029 is None:
        st.warning("2029년 데이터가 없습니다. _GAP_YEARS 범위를 확인하세요.")
    else:
        equity_2029 = row_2029["내 자기자본"]
        if gap_2029 > equity_2029 * 0.6:
            st.error(...)
        else:
            st.success(...)

    # ── Plotly 라인차트 ───────────────────────────────────────
    fig_gap = make_gap_chart(gap_df, target_year=2029)
    st.plotly_chart(fig_gap, use_container_width=True)

    # ── 데이터 테이블 ─────────────────────────────────────────
    st.dataframe(gap_df, use_container_width=True, hide_index=True)

    # ── 경고 로직 ─────────────────────────────────────────────
    equity_2029 = row_2029["내 자기자본"]
    if gap_2029 > equity_2029 * 0.6:
        st.error(
            f"상급지 이동 위험: 2029년 Gap {gap_2029:.2f}억이 자기자본({equity_2029:.2f}억)의 60%를 초과합니다. "
            "추가 저축 또는 수익률 제고 필요"
        )
    else:
        st.success(
            f"현재 저축 속도로 상급지 진입 가능 (2029년 Gap {gap_2029:.2f}억 / 자기자본 {equity_2029:.2f}억)"
        )

    # ── 의정부 매수 기회비용 (expander) ──────────────────────
    with st.expander("의정부 매수 시 취득세 기회비용 계산"):
        tax_rate = st.slider(
            "취득세율 (%)", min_value=1.0, max_value=3.0, value=1.0, step=0.5,
            key="gap_tax_rate"
        )
        acquisition_tax = _UI_PRICE_0 * 1e8 * (tax_rate / 100)
        opp = int(_opp_cost(acquisition_tax, _EQUITY_RATE, 3))

        st.metric("취득세", f"{acquisition_tax:,.0f}원")
        st.metric(
            "3년 연 3% 복리 운용 시 기회비용",
            f"{opp:,.0f}원",
            delta=f"+{opp:,.0f}원",
        )
        st.info(f"이 돈을 파킹하면 {opp:,.0f}원 더 모을 수 있습니다.")


# ── DSR 시뮬레이터 ───────────────────────────────────────────────
with st.expander("DSR 시뮬레이터 (매수 구매력 계산)"):
    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
        dsr_income = st.number_input(
            "예상 가구 월소득 (원)",
            min_value=0, value=10_800_000, step=10_000, format="%d",
            key="dsr_income"
        )
        st.caption(f"= {format_korean(dsr_income)}")
    with d_col2:
        dsr_rate = st.slider(
            "대출 금리 (%)", min_value=2.0, max_value=7.0, value=4.0, step=0.1,
            key="dsr_rate"
        )
    with d_col3:
        dsr_years = st.selectbox("대출 기간", [5, 10, 20, 25, 30, 40], index=2, key="dsr_years")

    max_loan  = calculate_max_loan(dsr_income, dsr_rate, dsr_years)
    total_buy = TARGET_EQUITY + max_loan
    buy_gap   = total_buy - TARGET_PRICE_HIGH

    m1, m2, m3 = st.columns(3)
    m1.metric("DSR 40% 최대 대출금", f"{max_loan:,}원")
    m2.metric("총 매수 가능 금액 (자기 자본 + 최대 대출금)", f"{total_buy:,}원")
    m3.metric(
        f"목표 {TARGET_PRICE_HIGH/1e8:.1f}억 대비 Gap",
        f"{buy_gap:+,}원",
        delta_color="normal" if buy_gap >= 0 else "inverse"
    )

    if buy_gap >= 0:
        st.success(f"목표 매수가 {TARGET_PRICE_HIGH:,}원 달성 가능")
    else:
        st.warning(f"목표 매수가 대비 {abs(buy_gap):,}원 부족")


# ============================================================
# 실행 전 사전 준비
# ============================================================
# 1. API 키 발급 (무료)
#    https://www.data.go.kr → "국토교통부 아파트매매 실거래가 상세자료" 활용신청
#    발급 후 Decoding 키 복사
#
# 2. secrets.toml 설정
#    .streamlit/secrets.toml 파일에 아래 추가:
#    [default]
#    MOLIT_API_KEY = "발급받은_Decoding_키"
#
# 3. API 없이도 하드코딩 폴백 데이터로 전체 UI 동작 확인 가능
# ============================================================
#
# git add pages/real_estate.py pages/cashflow.py
# git commit -m "feat: 부동산 전략 3종 세트 — 구매력/스코어카드/Gap트래커 추가"
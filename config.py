# config.py
from dotenv import load_dotenv
import os
load_dotenv()

# ── 가구 프로필 (환경변수 우선, 없으면 임의의 값) ──
MONTHLY_INCOME           = int(os.getenv("MONTHLY_INCOME",           7_000_000))
CURRENT_INVESTMENT       = int(os.getenv("CURRENT_INVESTMENT",       50_000_000))
CURRENT_CHONGSEK_DEPOSIT = int(os.getenv("CURRENT_CHONGSEK_DEPOSIT", 200_000_000))
CURRENT_SAVINGS_DEPOSIT  = int(os.getenv("CURRENT_SAVINGS_DEPOSIT",  20_000_000))
MONTHLY_SAVING_TARGET    = int(os.getenv("MONTHLY_SAVING_TARGET",    3_250_000))
TARGET_EQUITY            = int(os.getenv("TARGET_EQUITY",            500_000_000))
TARGET_PRICE_LOW         = int(os.getenv("TARGET_PRICE_LOW",         800_000_000))
TARGET_PRICE_HIGH        = int(os.getenv("TARGET_PRICE_HIGH",        850_000_000))
VARIABLE_BUDGET_LIMIT    = int(os.getenv("VARIABLE_BUDGET_LIMIT",    3_850_000))
TARGET_DATE_YEAR         = int(os.getenv("TARGET_DATE_YEAR",         2029))
TARGET_DATE_MONTH        = int(os.getenv("TARGET_DATE_YEAR",         2))
MORTGAGE_RATE            = int(os.getenv("TARGET_DATE_YEAR",         2))
MORTGAGE_YEARS           = int(os.getenv("TARGET_DATE_YEAR",         30))
DSR_LIMIT                = int(os.getenv("TARGET_DATE_YEAR",         0.40))
AREA_M2                  = int(os.getenv("TARGET_DATE_YEAR",         84))
PYEONG                   = int(os.getenv("TARGET_DATE_YEAR",         AREA_M2 / 3.305))

TARGET_PURCHASE_PRICE    = int(os.getenv("TARGET_PURCHASE_PRICE",   825_000_000))
TARGET_AREA_M2           = int(os.getenv("TARGET_AREA_M2",          84))
RETIREMENT_YEAR          = int(os.getenv("RETIREMENT_YEAR",         2048))
CURRENT_AGE              = int(os.getenv("CURRENT_AGE",             38))
ANNUAL_RETURN_RATE       = float(os.getenv("ANNUAL_RETURN_RATE",    0.06))
TARGET_DATE_YEAR         = int(os.getenv("TARGET_DATE_YEAR",        2029))
TARGET_DATE_MONTH        = int(os.getenv("TARGET_DATE_MONTH",       2))

# .env에 없는 파생 상수 (계산값이라 환경변수 불필요)
AREA_PER_PYEONG          = 3.305
TARGET_AREA_PYEONG       = TARGET_AREA_M2 / AREA_PER_PYEONG
PRICE_PER_PYEONG         = TARGET_PURCHASE_PRICE / TARGET_AREA_PYEONG

# 기본 카테고리 딕셔너리 (필수/선택 분류)
DEFAULT_CATEGORIES = {
    "필수소비 (Needs)": [
        "생활소비", 
        "의료/미용", 
        "교통비", 
        "공과금/주거",  
        "경조/교제비"
    ],
    "선택소비 (Wants)": [
        "외식/음료/간식", 
        "내구소비", 
        "쇼핑", 
        "문화/교육",                
        "기타"
    ]
}

def get_flat_categories():
    """딕셔너리에 있는 모든 카테고리를 하나의 리스트로 합쳐서 반환합니다."""
    flat_list = []
    for cat_list in DEFAULT_CATEGORIES.values():
        flat_list.extend(cat_list)
    return flat_list

# ==========================================
# [연도별] 3인 가구 기준중위소득 및 10분위 예산 통계
# ==========================================

# 연도별 3인 가구 기준중위소득 (보건복지부 고시 기준)
# [핵심 수정됨] 반드시 딕셔너리 형태여야 에러가 나지 않습니다.
MEDIAN_INCOME_3PERSON = {
    2025: 5086879,
    2026: 5300000
}

# 연도별 10분위 예산 추천 데이터
INCOME_DECILES_BUDGET = {
    2026: {
        "1분위 (하위 10%, 월 ~200만)": {
            "생활소비": 450000, "의료/미용": 50000, "교통비": 100000, "공과금/주거": 300000, "경조/교제비": 30000,
            "외식/음료/간식": 100000, "내구소비": 20000, "쇼핑": 30000, "문화/교육": 20000, "기타": 20000
        },
        "2분위 (월 ~300만)": {
            "생활소비": 600000, "의료/미용": 70000, "교통비": 120000, "공과금/주거": 350000, "경조/교제비": 50000,
            "외식/음료/간식": 150000, "내구소비": 30000, "쇼핑": 50000, "문화/교육": 50000, "기타": 30000
        },
        "3분위 (월 ~400만)": {
            "생활소비": 750000, "의료/미용": 100000, "교통비": 150000, "공과금/주거": 400000, "경조/교제비": 70000,
            "외식/음료/간식": 200000, "내구소비": 50000, "쇼핑": 80000, "문화/교육": 100000, "기타": 50000
        },
        "4분위 (월 ~470만)": {
            "생활소비": 850000, "의료/미용": 120000, "교통비": 180000, "공과금/주거": 450000, "경조/교제비": 100000,
            "외식/음료/간식": 250000, "내구소비": 80000, "쇼핑": 120000, "문화/교육": 150000, "기타": 50000
        },
        "5분위 (중위소득 근접, 월 ~530만)": {
            "생활소비": 1000000, "의료/미용": 150000, "교통비": 200000, "공과금/주거": 500000, "경조/교제비": 150000,
            "외식/음료/간식": 350000, "내구소비": 100000, "쇼핑": 150000, "문화/교육": 200000, "기타": 100000
        },
        "6분위 (월 ~600만)": {
            "생활소비": 1100000, "의료/미용": 180000, "교통비": 220000, "공과금/주거": 550000, "경조/교제비": 200000,
            "외식/음료/간식": 400000, "내구소비": 120000, "쇼핑": 200000, "문화/교육": 250000, "기타": 100000
        },
        "7분위 (월 ~700만)": {
            "생활소비": 1200000, "의료/미용": 200000, "교통비": 250000, "공과금/주거": 600000, "경조/교제비": 250000,
            "외식/음료/간식": 500000, "내구소비": 150000, "쇼핑": 250000, "문화/교육": 350000, "기타": 100000
        },
        "8분위 (월 ~850만)": {
            "생활소비": 1350000, "의료/미용": 250000, "교통비": 280000, "공과금/주거": 650000, "경조/교제비": 300000,
            "외식/음료/간식": 600000, "내구소비": 200000, "쇼핑": 350000, "문화/교육": 450000, "기타": 150000
        },
        "9분위 (월 ~1000만)": {
            "생활소비": 1500000, "의료/미용": 300000, "교통비": 320000, "공과금/주거": 700000, "경조/교제비": 400000,
            "외식/음료/간식": 750000, "내구소비": 250000, "쇼핑": 450000, "문화/교육": 600000, "기타": 200000
        },
        "10분위 (상위 10%, 월 1000만+)": {
            "생활소비": 1800000, "의료/미용": 400000, "교통비": 400000, "공과금/주거": 800000, "경조/교제비": 500000,
            "외식/음료/간식": 1000000, "내구소비": 400000, "쇼핑": 600000, "문화/교육": 800000, "기타": 300000
        }
    },
    2025: {
        "1분위 (하위 10%, 월 ~190만)": {
            "생활소비": 430000, "의료/미용": 50000, "교통비": 90000, "공과금/주거": 280000, "경조/교제비": 30000,
            "외식/음료/간식": 90000, "내구소비": 20000, "쇼핑": 30000, "문화/교육": 20000, "기타": 20000
        },
        "3분위 (월 ~380만)": {
            "생활소비": 720000, "의료/미용": 90000, "교통비": 140000, "공과금/주거": 380000, "경조/교제비": 60000,
            "외식/음료/간식": 180000, "내구소비": 40000, "쇼핑": 70000, "문화/교육": 90000, "기타": 40000
        },
        "5분위 (중위소득 근접, 월 ~508만)": {
            "생활소비": 950000, "의료/미용": 140000, "교통비": 190000, "공과금/주거": 470000, "경조/교제비": 130000,
            "외식/음료/간식": 320000, "내구소비": 90000, "쇼핑": 130000, "문화/교육": 180000, "기타": 90000
        },
        "7분위 (월 ~670만)": {
            "생활소비": 1150000, "의료/미용": 180000, "교통비": 230000, "공과금/주거": 570000, "경조/교제비": 220000,
            "외식/음료/간식": 450000, "내구소비": 130000, "쇼핑": 230000, "문화/교육": 320000, "기타": 90000
        },
        "10분위 (상위 10%, 월 950만+)": {
            "생활소비": 1700000, "의료/미용": 380000, "교통비": 380000, "공과금/주거": 750000, "경조/교제비": 450000,
            "외식/음료/간식": 900000, "내구소비": 350000, "쇼핑": 550000, "문화/교육": 750000, "기타": 250000
        }
    }
}

def get_decile_summary(year, decile_name):
    """
    특정 연도와 소득 분위의 추천 예산을 분석하여 
    (총합, 필수소비 합계, 선택소비 합계)를 튜플로 반환합니다.
    """
    budgets = INCOME_DECILES_BUDGET.get(year, {}).get(decile_name, {})
    needs_cats = DEFAULT_CATEGORIES["필수소비 (Needs)"]
    wants_cats = DEFAULT_CATEGORIES["선택소비 (Wants)"]
    
    needs_total = sum(amt for cat, amt in budgets.items() if cat in needs_cats)
    wants_total = sum(amt for cat, amt in budgets.items() if cat in wants_cats)
    total = needs_total + wants_total
    
    return total, needs_total, wants_total


# ==========================================
# GEMINI Model
# ==========================================

GEMINI_MODEL_VER = 'gemini-2.5-flash'
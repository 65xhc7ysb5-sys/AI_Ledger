import streamlit as st
import pandas as pd
import sys
import os

# 상위 폴더 모듈 로드
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [중요] database.py에 이 함수들이 모두 있어야 합니다!
from database import load_data, delete_expense, update_expense, get_available_months

# [중요] config.py가 없다면 에러가 날 수 있으니, 없을 경우를 대비한 기본값 설정
try:
    from config import CATEGORIES
except ImportError:
    # config.py를 아직 안 만들었을 경우 기본값
    CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

st.set_page_config(page_title="가계부 대시보드", page_icon="📊", layout="wide")

st.title("📊 소비 분석 대시보드")

# --- 1. 사이드바 (조회 및 백업) ---
with st.sidebar:
    st.header("🔍 조회 설정")
    
    # 월 선택 필터
    available_months = get_available_months()
    if not available_months:
        selected_month = "전체 기간"
    else:
        options = ["전체 기간"] + available_months
        selected_month = st.selectbox("📅 월 선택", options, index=1 if len(options) > 1 else 0)

    st.divider()
    
    st.header("📂 데이터 관리")
    
    # 1. CSV 다운로드 (엑셀용)
    # (데이터 로드 후 df가 있을 때 활성화하기 위해 아래에서 처리하거나, 여기서 미리 로직 준비)
    
    # 2. [신규] DB 원본 백업
    st.subheader("🛡️ 시스템 백업")
    try:
        with open("ledger.db", "rb") as f:
            db_data = f.read()
            
        st.download_button(
            label="💾 데이터베이스 원본 백업 (.db)",
            data=db_data,
            file_name="ledger_backup.db",
            mime="application/octet-stream",
            help="이 파일을 잘 보관하면 나중에 데이터를 통째로 복구할 수 있습니다."
        )
    except FileNotFoundError:
        st.warning("아직 생성된 DB 파일이 없습니다.")

# --- 2. 데이터 로드 ---
df = load_data(selected_month)
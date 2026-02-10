import sys
import os
from PIL import Image
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

import streamlit as st
from google import genai

# [수정] 데이터를 조회하기 위해 load_data, get_budgets 추가
from database import init_db, insert_expense, load_data, get_budgets 
# Categories 불러오기
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import CATEGORIES

# --- 1. 설정 및 초기화 ---
st.set_page_config(page_title="AI 가계부 - 홈", page_icon="🏠")

# 앱 시작 시 DB 초기화
try:
    init_db()
except Exception as e:
    st.error(f"초기화 오류: {e}")

# API 키 설정 (기존과 동일)
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.error("⚠️ API 키가 없습니다.")
        st.stop()
        
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"⚠️ 설정 오류: {e}")
    st.stop()

default_model_name = 'gemini-2.5-flash'

# --- 2. [신규] 상단 요약 대시보드 (HUD) ---
st.title("🏠 나의 자산 현황")

# 날짜 기준
today = datetime.now()
current_month_str = today.strftime("%Y-%m")
today_str = today.strftime("%Y-%m-%d")

# 데이터 가져오기
month_df = load_data(current_month_str)
budget_df = get_budgets()

# 계산 로직
total_spent_month = month_df['amount'].sum() if not month_df.empty else 0
total_budget = budget_df['amount'].sum() if not budget_df.empty else 0

# 오늘 지출 계산
if not month_df.empty:
    today_spent = month_df[month_df['date'].str.startswith(today_str)]['amount'].sum()
else:
    today_spent = 0

# UI: 3단 컬럼으로 핵심 지표 표시
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("📅 이번 달 지출", f"{total_spent_month:,}원")

with col2:
    if total_budget > 0:
        remaining = total_budget - total_spent_month
        st.metric("💰 남은 예산", f"{remaining:,}원", delta=remaining, delta_color="normal")
    else:
        st.metric("💰 예산 미설정", "-")

with col3:
    st.metric("🔥 오늘 쓴 돈", f"{today_spent:,}원")

st.divider()

# --- 3. 입력 UI (기존 코드 유지) ---
st.subheader("📝 새 내역 기록")

input_type = st.radio("입력 방식", ["텍스트", "이미지 캡처"], horizontal=True, label_visibility="collapsed")

with st.form("expense_form", clear_on_submit=False):
    user_content = None
    content_type = None
    
    if input_type == "텍스트":
        user_content = st.text_area("내용 입력", height=100, placeholder="예: 오늘 점심 순대국 9000원")
        content_type = 'text'
    else:
        uploaded_file = st.file_uploader("영수증/이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            user_content = Image.open(uploaded_file)
            content_type = 'image'
            st.image(user_content, caption="업로드된 이미지", width=300)
    
    st.write("")
    c1, c2 = st.columns([1, 2])
    with c1:
        installment_months = st.selectbox("할부(개월)", options=[1] + list(range(2, 13)))
    with c2:
        st.write("")
        st.write("")
        submitted = st.form_submit_button("기록하기 🚀", use_container_width=True)

# --- 4. 실행 로직 (기존과 동일, 프롬프트 개선 버전) ---
if submitted:
    if not user_content:
        st.warning("⚠️ 내용을 입력해주세요.")
    else:
        with st.status("AI가 분석 중입니다...", expanded=True) as status:
            try:
                # 날짜 동적 처리
                status.write("⚙️ 1단계: 날짜 기준 설정 중...")
                
                prompt = f"""
                당신은 가계부 정리 전문가입니다. 입력된 정보에서 다음 데이터를 추출해 JSON 형식으로만 응답하세요.
                
                [기준 정보]
                - 작성 기준일: {today_str} (별도 언급 없으면 이 날짜 사용)
                - 기준 연도: {today.year}년
                
                [추출 항목]
                1. date (YYYY-MM-DD 형식. 예: '어제' -> 계산해서 입력)
                2. item (구매 항목 이름)
                3. amount (금액, 숫자만, '원' 제외)
                4. category (반드시 다음 중 선택: {CATEGORIES})
                
                JSON 예시: {{"date": "{today_str}", "item": "커피", "amount": 4500, "category": "외식"}}
                응답은 반드시 순수한 JSON 문자열이어야 합니다.
                """
                
                if content_type == 'text':
                    contents = [prompt + "\n\n" + user_content]
                else:
                    contents = [prompt, user_content]
                
                status.write("📡 2단계: Gemini에게 물어보는 중...")
                response = client.models.generate_content(
                    model=default_model_name,
                    contents=contents
                )
                
                status.write("🔍 3단계: 데이터 정리 중...")
                if not response.text:
                    raise ValueError("응답이 비어있습니다.")
                    
                clean_res = response.text.replace("```json", "").replace("```", "").strip()
                raw_data = json.loads(clean_res)
                
                new_entries = []
                items = raw_data if isinstance(raw_data, list) else [raw_data]
                
                for item in items:
                    safe_entry = {
                        "date": item.get("date", today_str),
                        "item": item.get("item", "알 수 없음"),
                        "amount": int(str(item.get("amount", 0)).replace(",","")), 
                        "category": item.get("category", "기타")
                    }
                    new_entries.append(safe_entry)
                
                # 할부 로직
                final_entries = []
                if installment_months > 1:
                    status.write(f"➗ {installment_months}개월 할부 적용 중...")
                    for entry in new_entries:
                        total_amt = entry['amount']
                        try:
                            base_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                        except:
                            base_date = datetime.now()
                            
                        monthly_amt = total_amt // installment_months
                        for i in range(installment_months):
                            next_date = base_date + relativedelta(months=i)
                            inst_entry = entry.copy()
                            inst_entry['date'] = next_date.strftime("%Y-%m-%d")
                            inst_entry['amount'] = monthly_amt
                            inst_entry['item'] = f"{entry['item']} ({i+1}/{installment_months})"
                            final_entries.append(inst_entry)
                else:
                    final_entries = new_entries
                
                status.write("💾 4단계: 저장 중...")
                if insert_expense(final_entries):
                    status.update(label="완료!", state="complete", expanded=False)
                    st.success("✅ 저장되었습니다!")
                    st.rerun() # [중요] 저장 후 화면을 새로고침해야 상단 지표가 바로 바뀝니다!
                else:
                    st.error("저장 실패")
                    
            except Exception as e:
                st.error(f"오류: {e}")
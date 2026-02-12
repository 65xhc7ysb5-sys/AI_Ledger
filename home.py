import streamlit as st
from google import genai
import os
from PIL import Image
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
# get_categories가 추가되었습니다.
from database import init_db, insert_expense, load_data, get_budgets, get_categories

st.set_page_config(page_title="AI 가계부 - 홈", page_icon="🏠")

# 앱 시작 시 DB 초기화 (카테고리 테이블 생성 등)
init_db()

# --- (API 키 설정 코드는 기존과 동일하므로 생략) ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
except:
    st.stop()
    
default_model_name = 'gemini-2.5-flash'

# --- 2. 상단 요약 (HUD) ---
st.title("🏠 나의 자산 현황")
today = datetime.now()
current_month_str = today.strftime("%Y-%m")
today_str = today.strftime("%Y-%m-%d")

# [수정] DB에서 카테고리 목록을 실시간으로 가져옴
CATEGORIES = get_categories()
if not CATEGORIES:
    CATEGORIES = ["미분류"] # 비상용

# 데이터 로드 (전체 보기 기준)
month_df = load_data(current_month_str) 
budget_df = get_budgets()

total_spent_month = month_df['amount'].sum() if not month_df.empty else 0
total_budget = budget_df['amount'].sum() if not budget_df.empty else 0

if not month_df.empty:
    today_spent = month_df[month_df['date'].str.startswith(today_str)]['amount'].sum()
else:
    today_spent = 0

col1, col2, col3 = st.columns(3)
col1.metric("📅 이번 달 지출", f"{total_spent_month:,}원")
remaining = total_budget - total_spent_month
col2.metric("💰 남은 예산", f"{remaining:,}원", delta=remaining)
col3.metric("🔥 오늘 쓴 돈", f"{today_spent:,}원")

st.divider()

# --- 3. 입력 UI ---
st.subheader("📝 새 내역 기록")

input_type = st.radio("입력 방식", ["텍스트", "이미지 캡처"], horizontal=True, label_visibility="collapsed")

with st.form("expense_form", clear_on_submit=False):
    # [핵심 추가] 지출 주체 선택
    st.write("👤 **누가 썼나요?**")
    spender = st.radio("지출 주체", ["공동", "남편", "아내", "아이"], horizontal=True, label_visibility="collapsed")
    
    st.write("---")
    
    user_content = None
    content_type = None
    if input_type == "텍스트":
        user_content = st.text_area("내용 입력", height=100, placeholder="예: 오늘 점심 순대국 9000원")
        content_type = 'text'
    else:
        uploaded_file = st.file_uploader("이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            user_content = Image.open(uploaded_file)
            content_type = 'image'
            st.image(user_content, caption="업로드된 이미지", width=300)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        installment_months = st.selectbox("할부(개월)", options=[1] + list(range(2, 13)))
    with col2:
        st.write("") 
        st.write("")
        submitted = st.form_submit_button("기록하기 🚀", use_container_width=True)

# --- 4. 실행 로직 ---
if submitted:
    if not user_content:
        st.warning("⚠️ 내용을 입력해주세요.")
    else:
        with st.status("AI가 분석 중입니다...", expanded=True) as status:
            try:
                status.write("⚙️ 1단계: 날짜 및 분류 기준 설정...")
                # 프롬프트에 DB에서 가져온 최신 CATEGORIES를 넣어줍니다.
                prompt = f"""
                당신은 가계부 정리 전문가입니다. 
                
                [기준 정보]
                - 작성 기준일: {today_str}
                - 기준 연도: {today.year}년
                - 가능 카테고리: {", ".join(CATEGORIES)} (이 중에서만 선택, 없으면 '기타')
                
                [추출 항목]
                1. date (YYYY-MM-DD)
                2. item (항목명)
                3. amount (금액, 숫자만)
                4. category (위 목록 중 하나)
                
                JSON 예시: {{"date": "{today_str}", "item": "커피", "amount": 4500, "category": "외식"}}
                """
                
                if content_type == 'text':
                    contents = [prompt + "\n\n" + user_content]
                else:
                    contents = [prompt, user_content]
                
                status.write("📡 2단계: Gemini 분석 중...")
                response = client.models.generate_content(
                    model=default_model_name,
                    contents=contents
                )
                
                clean_res = response.text.replace("```json", "").replace("```", "").strip()
                raw_data = json.loads(clean_res)
                
                new_entries = []
                items = raw_data if isinstance(raw_data, list) else [raw_data]
                
                for item in items:
                    safe_entry = {
                        "date": item.get("date", today_str),
                        "item": item.get("item", "알 수 없음"),
                        "amount": int(str(item.get("amount", 0)).replace(",","")), 
                        "category": item.get("category", "기타"),
                        "spender": spender # [중요] 사용자가 선택한 주체 할당
                    }
                    new_entries.append(safe_entry)
                
                # 할부 로직 (기존 유지)
                final_entries = []
                if installment_months > 1:
                    for entry in new_entries:
                        total_amt = entry['amount']
                        try: base_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                        except: base_date = datetime.now()
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
                    st.success(f"✅ [{spender}] 명의로 저장되었습니다!")
                    st.rerun()
                else:
                    st.error("저장 실패")
            except Exception as e:
                st.error(f"오류: {e}")
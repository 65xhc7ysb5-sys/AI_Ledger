import streamlit as st
from google import genai
import os
from PIL import Image
import json
from database import init_db, insert_expense

# --- 1. 설정 및 초기화 ---
st.set_page_config(page_title="AI 가계부 - 입력", page_icon="📝")

# 앱 시작 시 DB 초기화
try:
    init_db()
except Exception as e:
    st.error(f"초기화 오류: 데이터베이스를 연결할 수 없습니다. {e}")

# API 키 및 클라이언트 설정
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.error("⚠️ API 키가 없습니다. .streamlit/secrets.toml 파일을 확인해주세요.")
        st.stop()
        
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"⚠️ 설정 오류: {e}")
    st.stop()

default_model_name = 'gemini-2.5-flash'

# --- 2. UI 구성 ---
st.title("📝 가계부 입력")
st.caption("내용을 입력하고 기록하기 버튼을 눌러주세요.")

CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

# 입력 방식 선택 (폼 바깥에 둬야 선택 시 즉시 화면이 바뀝니다)
input_type = st.radio("입력 방식", ["텍스트", "이미지 캡처"], horizontal=True)

# [핵심 수정] st.form으로 입력 영역 감싸기
with st.form("expense_form", clear_on_submit=False):
    user_content = None
    content_type = None
    
    if input_type == "텍스트":
        # 텍스트 입력 시 엔터(Command+Enter)로도 제출 가능해짐
        user_content = st.text_area("내용 입력", height=150, placeholder="예: 오늘 점심 중국집 18000원")
        content_type = 'text'
    else:
        uploaded_file = st.file_uploader("이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            user_content = Image.open(uploaded_file)
            content_type = 'image'
            st.image(user_content, caption="업로드된 이미지", width=300)
    
    # [핵심 수정] 일반 button 대신 form_submit_button 사용
    submitted = st.form_submit_button("기록하기 🚀", use_container_width=True)

# --- 3. 실행 로직 (버튼 클릭 시에만 실행) ---
if submitted:
    if not user_content:
        st.warning("⚠️ 내용을 입력하거나 이미지를 올려주세요.")
    else:
        # 상태 표시창
        with st.status("AI가 데이터를 분석하고 있습니다...", expanded=True) as status:
            try:
                # 1단계: 프롬프트 구성
                status.write("⚙️ 1단계: Gemini에게 보낼 데이터 준비 중...")
                prompt = f"""
                당신은 가계부 정리 전문가입니다. 입력된 정보에서 다음 데이터를 추출해 JSON 형식으로만 응답하세요.
                1. date (YYYY-MM-DD 형식, 날짜가 없으면 오늘 날짜 2026-01-30 사용)
                2. item (구매 항목 이름)
                3. amount (금액, 숫자만, '원' 제외)
                4. category (반드시 다음 중 선택: {CATEGORIES})
                
                JSON 예시: {{"date": "2026-01-30", "item": "짜장면", "amount": 18000, "category": "외식"}}
                응답은 반드시 순수한 JSON 문자열이어야 합니다.
                """
                
                if content_type == 'text':
                    contents = [prompt + "\n\n" + user_content]
                else:
                    contents = [prompt, user_content]
                
                # 2단계: API 호출
                status.write("📡 2단계: Google Gemini API 호출 중...")
                response = client.models.generate_content(
                    model=default_model_name,
                    contents=contents
                )
                
                # 3단계: 결과 파싱
                status.write("🔍 3단계: 응답 데이터 해석 중...")
                if not response.text:
                    raise ValueError("Gemini로부터 빈 응답이 왔습니다.")
                    
                clean_res = response.text.replace("```json", "").replace("```", "").strip()
                raw_data = json.loads(clean_res)
                
                new_entries = []
                items = raw_data if isinstance(raw_data, list) else [raw_data]
                
                for item in items:
                    safe_entry = {
                        "date": item.get("date", "2026-01-30"),
                        "item": item.get("item", "알 수 없음"),
                        "amount": int(str(item.get("amount", 0)).replace(",","")), 
                        "category": item.get("category", "기타")
                    }
                    new_entries.append(safe_entry)
                
                status.write(f"✅ 데이터 추출 성공: {len(new_entries)}건")
                
                # 4단계: DB 저장
                status.write("💾 4단계: 내 컴퓨터(SQLite)에 저장 중...")
                if insert_expense(new_entries):
                    status.update(label="🎉 모든 작업이 완료되었습니다!", state="complete", expanded=False)
                    st.success(f"✅ 저장 성공! ({new_entries[0]['item']} - {new_entries[0]['amount']:,}원)")
                    
                    # 저장된 데이터 확인용 출력
                    st.json(new_entries)
                else:
                    status.update(label="❌ 저장 실패", state="error")
                    st.error("데이터베이스 저장에 실패했습니다.")
                    
            except Exception as e:
                status.update(label="❌ 처리 중 오류 발생", state="error")
                st.error(f"상세 에러 내용: {e}")
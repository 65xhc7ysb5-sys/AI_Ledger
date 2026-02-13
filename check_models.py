import os
import streamlit as st
from google import genai

# 1. API 키 가져오기
api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except:
    pass

if not api_key:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API 키를 찾을 수 없습니다. 환경변수나 .streamlit/secrets.toml을 확인해주세요.")
else:
    print(f"🔑 API Key 확인됨 (앞 4자리: {api_key[:4]}...)")
    print("📡 모델 목록을 조회합니다...\n")
    
    try:
        client = genai.Client(api_key=api_key)
        
        count = 0
        # 필터링 없이 모든 모델 출력 (오류 방지)
        for model in client.models.list():
            print(f"✅ 모델명: {model.name}")
            
            # 추가 정보가 있다면 출력 (없어도 에러 안 나게 처리)
            if hasattr(model, 'display_name'):
                print(f"   - 설명: {model.display_name}")
            
            print("-" * 30)
            count += 1
        
        if count == 0:
            print("⚠️ 조회된 모델이 없습니다. API 키 권한을 확인해주세요.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
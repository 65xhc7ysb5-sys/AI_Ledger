import google.genai as genai
import os
import pandas as pd
from PIL import Image
import json

# Streamlit이 있는 경우에만 import
try:
    import streamlit as st
    from audio_recorder_streamlit import audio_recorder
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None
    audio_recorder = None

# 1. 보안 설정: Secrets에서 API 키 가져오기
try:
    if STREAMLIT_AVAILABLE:
        # Streamlit 환경에서는 secrets에서 가져오기
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        # Streamlit이 아닌 환경에서는 환경 변수 또는 secrets 파일에서 가져오기
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # secrets.toml 파일에서 직접 읽기 시도
            secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                try:
                    import tomllib  # Python 3.11+
                except ImportError:
                    try:
                        import tomli as tomllib  # Python < 3.11
                    except ImportError:
                        tomllib = None
                
                if tomllib:
                    with open(secrets_path, "rb") as f:
                        secrets = tomllib.load(f)
                        api_key = secrets.get("GEMINI_API_KEY")
                
                if not api_key:
                    # 간단한 파싱 (toml 라이브러리가 없는 경우)
                    with open(secrets_path, "r") as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY"):
                                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY를 찾을 수 없습니다.")
except (KeyError, AttributeError, ValueError) as e:
    error_msg = "오류: API 키를 찾을 수 없습니다. .streamlit/secrets.toml 또는 GEMINI_API_KEY 환경 변수를 설정하세요."
    if STREAMLIT_AVAILABLE:
        st.error(error_msg)
        st.stop()
    else:
        print(error_msg)
        exit(1)

try:
    # 새 google.genai 패키지의 Client 사용
    client = genai.Client(api_key=api_key)
except Exception as e:
    error_msg = f"API 클라이언트 초기화 오류: {e}"
    if STREAMLIT_AVAILABLE:
        st.error(error_msg)
        st.stop()
    else:
        print(error_msg)
        exit(1)

# 2. Gemini 모델 설정
# gemini-2.5-flash를 기본으로 사용 (빠르고 비용 효율적)
default_model_name = 'gemini-2.5-flash'

# 앱 UI 구성
st.set_page_config(page_title="정훈님의 AI 가계부", layout="wide")
st.title("💰 AI 가계부: 캡처 한 장으로 끝내기")
st.info("텍스트를 입력하거나 영수증/카드 결제 캡처 사진을 올려보세요.")

# 사이드바: 카테고리 관리
CATEGORIES = ["외식", "식자재", "교통비", "생활비", "육아", "쇼핑", "주거", "의료", "공과금", "기타"]

# 입력 섹션
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 내역 입력")
    input_type = st.radio("입력 방식", ["텍스트", "이미지 캡처"])
    
    user_content = None
    content_type = None  # 'text', 'audio', 'image'
    
    if input_type == "텍스트":
        # 텍스트 입력 탭
        user_content = st.text_area("내용을 입력하세요 (예: 오늘 점심 만두국 9,000원)", height=150)
        content_type = 'text'

    else:
        # 영수증 / 카드 내역 캡쳐본 입력 탭
        uploaded_file = st.file_uploader("영수증이나 카드 내역 캡처본을 올려주세요", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            user_content = Image.open(uploaded_file)
            content_type = 'image'
            st.image(user_content, caption="업로드된 이미지", use_container_width=True)

# 분석 로직
if st.button("AI 분석 및 기록하기 🚀"):
    if not user_content:
        st.warning("분석할 내용을 입력해주세요.")
    else:
        with st.spinner("Gemini가 데이터를 읽고 분류하는 중..."):
            prompt = f"""
            당신은 가계부 정리 전문가입니다. 입력된 정보에서 다음 데이터를 추출해 JSON 형식으로만 응답하세요.
            1. date (YYYY-MM-DD 형식, 날짜가 없으면 오늘 날짜 2026-01-24 사용)
            2. item (구매 항목 이름)
            3. amount (금액, 숫자만)
            4. category (반드시 다음 중 선택: {CATEGORIES})
            
            JSON 형식 예시:
            {{"date": "2026-01-24", "item": "항목명", "amount": 10000, "category": "식비"}}
            """
            
            try:
                # 새 google.genai 패키지의 Client API 사용
                # contents는 문자열, PIL Image, 오디오 파일 경로, 또는 리스트를 직접 전달할 수 있습니다
                if content_type == 'text':
                    # 텍스트 입력인 경우
                    contents = [prompt + "\n\n" + user_content]
                elif content_type == 'audio':
                    # 오디오 입력인 경우 - 파일 경로를 사용하여 처리
                    # 오디오 파일을 읽어서 처리
                    pass  # 아래에서 별도 처리
                else:
                    # 이미지 입력인 경우 - PIL Image를 직접 전달 가능
                    contents = [prompt, user_content]
                
                # 모델 호출
                # 오디오의 경우 특별 처리 필요
                if content_type == 'audio':
                    # 오디오 파일을 업로드하고 처리
                    try:
                        # File API를 사용하여 오디오 업로드
                        with open(user_content, 'rb') as f:
                            uploaded_file_obj = client.files.upload(path=user_content)
                        # 오디오 파일을 사용하여 콘텐츠 생성
                        response = client.models.generate_content(
                            model=default_model_name,
                            contents=[prompt, uploaded_file_obj]
                        )
                        # 임시 파일 정리
                        import os
                        if os.path.exists(user_content):
                            os.unlink(user_content)
                    except Exception as audio_error:
                        # File API가 지원되지 않는 경우, 오디오를 바이너리로 직접 전달 시도
                        try:
                            st.info("오디오를 직접 처리 중...")
                            with open(user_content, 'rb') as audio_file:
                                audio_bytes = audio_file.read()
                            # 오디오 바이너리를 직접 전달
                            import base64
                            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                            # Gemini가 오디오를 직접 처리할 수 있도록 시도
                            # 참고: 실제 API 구조에 따라 조정 필요
                            response = client.models.generate_content(
                                model=default_model_name,
                                contents=[prompt, {"mime_type": "audio/wav", "data": audio_bytes}]
                            )
                            import os
                            if os.path.exists(user_content):
                                os.unlink(user_content)
                        except Exception as e2:
                            st.warning(f"오디오 처리에 실패했습니다: {e2}")
                            st.info("💡 팁: 오디오 대신 텍스트로 직접 입력해주세요.")
                            response = None
                            import os
                            if os.path.exists(user_content):
                                os.unlink(user_content)
                else:
                    response = client.models.generate_content(
                        model=default_model_name,
                        contents=contents   
                    )
                
                if response is None:
                    # 오디오 처리 실패로 인한 None 응답
                    pass
                else:
                    # 응답 텍스트 추출
                    if hasattr(response, 'candidates') and response.candidates:
                        response_text = response.candidates[0].content.parts[0].text
                    elif hasattr(response, 'text'):
                        response_text = response.text
                    else:
                        response_text = str(response)            

                    # 결과 파싱 (마크다운 제거)
                    clean_res = response_text.replace("```json", "").replace("```", "").strip()
                    raw_data = json.loads(clean_res)
                    
                    # [수정된 부분] 리스트인지 딕셔너리인지 확인해서 유연하게 처리
                    new_entries = []
                    
                    if isinstance(raw_data, list):
                        # 리스트로 온 경우 (예: 영수증 하나에 품목이 여러 개일 때)
                        for item in raw_data:
                            safe_entry = {
                                "date": item.get("date", "2026-01-24"),
                                "item": item.get("item", "알 수 없음"),
                                "amount": item.get("amount", 0),
                                "category": item.get("category", "기타")
                            }
                            new_entries.append(safe_entry)
                    else:
                        # 딕셔너리(단일 항목)로 온 경우
                        safe_entry = {
                            "date": raw_data.get("date", "2026-01-24"),
                            "item": raw_data.get("item", "알 수 없음"),
                            "amount": raw_data.get("amount", 0),
                            "category": raw_data.get("category", "기타")
                        }
                        new_entries.append(safe_entry)
                    
                    # 세션 상태에 저장 (휘발성 방지)
                    if 'ledger' not in st.session_state:
                        st.session_state.ledger = []
                    
                    # 새로 만든 리스트를 기존 장부에 추가
                    st.session_state.ledger.extend(new_entries)
                    
                    st.success(f"{len(new_entries)}건의 기록이 완료되었습니다!")
                
            except Exception as e:
                # 모델이 사용 불가능한 경우 다른 모델로 재시도
                error_str = str(e)
                
                if "404" in error_str or "NOT_FOUND" in error_str or "not found" in error_str.lower() or "model" in error_str.lower():
                    try:
                        st.info("모델을 변경하여 재시도 중...")
                        # gemini-1.5-pro로 재시도
                        fallback_model_name = 'gemini-1.5-pro'
                        
                        if content_type == 'text':
                            contents = [prompt + "\n\n" + user_content]
                        elif content_type == 'audio':
                            # 오디오는 fallback 모델에서도 동일하게 처리
                            try:
                                with open(user_content, 'rb') as f:
                                    uploaded_file_obj = client.files.upload(path=user_content)
                                response = client.models.generate_content(
                                    model=fallback_model_name,
                                    contents=[prompt, uploaded_file_obj]
                                )
                                import os
                                if os.path.exists(user_content):
                                    os.unlink(user_content)
                            except Exception as e_audio:
                                try:
                                    # 대체 방법 시도
                                    with open(user_content, 'rb') as audio_file:
                                        audio_bytes = audio_file.read()
                                    response = client.models.generate_content(
                                        model=fallback_model_name,
                                        contents=[prompt, {"mime_type": "audio/wav", "data": audio_bytes}]
                                    )
                                    import os
                                    if os.path.exists(user_content):
                                        os.unlink(user_content)
                                except Exception:
                                    st.warning("오디오 처리에 실패했습니다.")
                                    response = None
                                    import os
                                    if os.path.exists(user_content):
                                        os.unlink(user_content)
                            if response is None:
                                # 오디오 처리 실패 시 더 이상 진행하지 않음
                                raise Exception("오디오 처리 실패")
                        else:
                            contents = [prompt, user_content]
                            response = client.models.generate_content(
                                model=fallback_model_name,
                                contents=contents
                            )
                        
                        if response is not None:
                            if hasattr(response, 'candidates') and response.candidates:
                                response_text = response.candidates[0].content.parts[0].text
                            elif hasattr(response, 'text'):
                                response_text = response.text
                            else:
                                response_text = str(response)
                            
                            clean_res = response_text.replace("```json", "").replace("```", "").strip()
                            data = json.loads(clean_res)
                            
                            if 'ledger' not in st.session_state:
                                st.session_state.ledger = []
                            st.session_state.ledger.append(data)
                            
                            st.success("기록 완료! (gemini-1.5-pro 모델 사용)")
                    except Exception as e2:
                        st.error(f"분석 오류: 사용 가능한 모델을 찾을 수 없습니다. {e2}")
                        st.info("💡 팁: API 키가 올바른지, 그리고 Gemini API에 접근 권한이 있는지 확인해주세요.")
                        st.exception(e2)
                else:
                    st.error(f"분석 오류: {e}")
                    st.exception(e)

# 결과 출력 섹션
with col2:
    st.subheader("📊 최근 기록")
    if 'ledger' in st.session_state and st.session_state.ledger:
        df = pd.DataFrame(st.session_state.ledger)
        
        # 삭제 기능 추가
        st.write("**내역 관리**")
        if len(df) > 0:
            # 각 항목에 대한 체크박스 생성
            selected_indices = []
            for idx in range(len(df)):
                row = df.iloc[idx]
                # 각 행을 표시하고 체크박스 추가
                col_check, col_info = st.columns([0.1, 0.9])
                with col_check:
                    if st.checkbox("", key=f"delete_{idx}"):
                        selected_indices.append(idx)
                with col_info:
                    st.write(f"**{row.get('item', 'N/A')}** | {row.get('amount', 0):,}원 | {row.get('category', 'N/A')} | {row.get('date', 'N/A')}")
            
            # 삭제 버튼
            if selected_indices:
                if st.button(f"선택한 {len(selected_indices)}개 항목 삭제", type="primary"):
                    # 선택된 인덱스를 역순으로 정렬하여 삭제 (인덱스 변경 방지)
                    for idx in sorted(selected_indices, reverse=True):
                        st.session_state.ledger.pop(idx)
                    st.success(f"{len(selected_indices)}개 항목이 삭제되었습니다.")
                    st.rerun()
        
        st.divider()
        st.write("**전체 내역**")
        df_display = pd.DataFrame(st.session_state.ledger)
        if len(df_display) > 0:
            st.dataframe(df_display, use_container_width=True)
            
            # 간단한 소비 차트 (안전장치 추가)
            if 'category' in df_display.columns and 'amount' in df_display.columns:
                st.bar_chart(df_display.groupby('category')['amount'].sum())
            else:
                st.warning("차트를 그리기 위한 데이터(카테고리/금액)가 충분하지 않습니다.")
                st.write("현재 데이터 구조:", df_display.columns.tolist()) # 디버깅용
                        
        else:
            st.write("아직 기록된 내역이 없습니다.")
    else:
        st.write("아직 기록된 내역이 없습니다.")
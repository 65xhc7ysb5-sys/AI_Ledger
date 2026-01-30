# test_db.py
from database import init_db, insert_expense, load_data, delete_expense
import os

print("--- 1. 데이터베이스 초기화 테스트 ---")
try:
    init_db()
    if os.path.exists("ledger.db"):
        print("✅ 성공: ledger.db 파일이 생성되었습니다.")
    else:
        print("❌ 실패: 파일이 생성되지 않았습니다.")
except Exception as e:
    print(f"❌ 에러 발생: {e}")

print("\n--- 2. 데이터 저장 테스트 ---")
sample_data = [{
    "date": "2026-01-30",
    "item": "테스트 커피",
    "amount": 5000,
    "category": "외식"
}]
try:
    if insert_expense(sample_data):
        print("✅ 성공: 데이터가 저장되었습니다.")
    else:
        print("❌ 실패: 저장 함수가 False를 반환했습니다.")
except Exception as e:
    print(f"❌ 에러 발생: {e}")

print("\n--- 3. 데이터 조회 테스트 ---")
try:
    df = load_data()
    print(f"현재 저장된 데이터 개수: {len(df)}개")
    if not df.empty and df.iloc[0]['item'] == "테스트 커피":
        print("✅ 성공: 방금 저장한 데이터를 정확히 불러왔습니다.")
        print(df.head())
        
        # 테스트 데이터 삭제 (청소)
        print("\n--- 4. 삭제 테스트 ---")
        target_id = df.iloc[0]['id']
        delete_expense(target_id)
        df_after = load_data()
        if len(df_after) == len(df) - 1:
            print("✅ 성공: 데이터가 정상적으로 삭제되었습니다.")
        else:
            print("❌ 실패: 데이터가 삭제되지 않았습니다.")
            
    else:
        print("❌ 실패: 데이터가 비어있거나 내용이 다릅니다.")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
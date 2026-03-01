# config.py

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
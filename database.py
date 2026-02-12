import sqlite3
import pandas as pd
import streamlit as st
import os

# 현재 파일 위치 기준 절대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "ledger.db")

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # 컬럼명으로 접근 가능하게 설정
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. 일반 지출 테이블 (spender 추가됨)
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            item TEXT,
            amount INTEGER,
            category TEXT,
            spender TEXT DEFAULT '공동', -- [신규] 지출 주체 (공동/남편/아내/아이)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. 고정 지출 테이블 (spender 추가됨)
    c.execute('''
        CREATE TABLE IF NOT EXISTS fixed_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            spender TEXT DEFAULT '공동', -- [신규]
            payment_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. 예산 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            amount INTEGER
        )
    ''')
    
    # 4. [신규] 카테고리 관리 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            is_default INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # 초기 카테고리 세팅 (config.py에 있는 내용을 DB로 옮김)
    seed_categories()

def seed_categories():
    """DB에 카테고리가 하나도 없으면 config.py의 내용을 초기값으로 넣습니다."""
    try:
        from config import CATEGORIES
        current = get_categories()
        if not current:
            conn = get_connection()
            c = conn.cursor()
            for cat in CATEGORIES:
                c.execute("INSERT OR IGNORE INTO categories (name, is_default) VALUES (?, 1)", (cat,))
            conn.commit()
            conn.close()
    except ImportError:
        pass

# --- 카테고리 관리 함수 ---
def get_categories():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name FROM categories ORDER BY name", conn)
        return df['name'].tolist()
    except:
        return []
    finally:
        conn.close()

def add_category(new_category):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name) VALUES (?)", (new_category,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        st.warning("이미 존재하는 카테고리입니다.")
        return False
    finally:
        conn.close()

def delete_category_safe(category_name):
    """
    카테고리를 삭제하면, 해당 카테고리를 가진 모든 지출 내역을 '미분류'로 변경합니다.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. 해당 카테고리 내역을 '미분류'로 업데이트
        c.execute("UPDATE expenses SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("UPDATE fixed_expenses SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("UPDATE budgets SET category = '미분류' WHERE category = ?", (category_name,))
        
        # 2. 카테고리 삭제
        c.execute("DELETE FROM categories WHERE name = ?", (category_name,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"카테고리 삭제 실패: {e}")
        return False
    finally:
        conn.close()

# --- 일반 지출 함수 (spender 처리 추가) ---
def insert_expense(data_list):
    conn = get_connection()
    c = conn.cursor()
    try:
        for entry in data_list:
            # spender가 없으면 '공동'으로 기본값
            spender = entry.get('spender', '공동')
            c.execute('''
                INSERT INTO expenses (date, item, amount, category, spender)
                VALUES (?, ?, ?, ?, ?)
            ''', (entry['date'], entry['item'], entry['amount'], entry['category'], spender))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ DB 저장 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

def load_data(month_str=None, spender_filter=None):
    """
    spender_filter: '전체', '공동', '남편' 등 필터링 조건
    """
    conn = get_connection()
    try:
        query = "SELECT * FROM expenses WHERE 1=1"
        params = []
        
        if month_str and month_str != "전체 기간":
            query += " AND date LIKE ?"
            params.append(f"{month_str}%")
            
        if spender_filter and spender_filter != "전체":
            query += " AND spender = ?"
            params.append(spender_filter)
            
        query += " ORDER BY date DESC"
        
        df = pd.read_sql(query, conn, params=params)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

# --- 나머지 유틸리티 함수들 ---
def get_available_months():
    conn = get_connection()
    try:
        query = "SELECT DISTINCT substr(date, 1, 7) as month FROM expenses ORDER BY month DESC"
        df = pd.read_sql(query, conn)
        return df['month'].tolist()
    except:
        return []
    finally:
        conn.close()

def delete_expense(expense_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
        conn.commit()
    except Exception as e:
        st.error(f"삭제 실패: {e}")
    finally:
        conn.close()

def update_expense(expense_id, column, new_value):
    conn = get_connection()
    c = conn.cursor()
    try:
        query = f"UPDATE expenses SET {column} = ? WHERE id = ?"
        c.execute(query, (new_value, int(expense_id)))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"수정 실패: {e}")
        return False
    finally:
        conn.close()

# 고정 지출/예산 함수들도 spender/category 변화에 맞춰 유지하거나 수정 필요하지만
# 핵심 로직은 위와 동일하므로 일단 database.py는 여기까지가 핵심입니다.
# (budget 관련 get/save/delete 함수는 기존 코드 유지하되 DB 연결부만 위 방식 따름)
def save_budget(category, amount):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO budgets (category, amount) VALUES (?, ?)", (category, amount))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_budgets():
    conn = get_connection()
    try:
        return pd.read_sql("SELECT * FROM budgets", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def delete_budget(category):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM budgets WHERE category = ?", (category,))
        conn.commit()
    except: pass
    finally: conn.close()

def save_fixed_expense(item, amount, category, payment_day, spender='공동'):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO fixed_expenses (item, amount, category, spender, payment_day) 
                     VALUES (?, ?, ?, ?, ?)''', (item, amount, category, spender, payment_day))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_fixed_expenses():
    conn = get_connection()
    try:
        return pd.read_sql("SELECT * FROM fixed_expenses ORDER BY payment_day ASC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def delete_fixed_expense(fixed_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM fixed_expenses WHERE id = ?", (int(fixed_id),))
        conn.commit()
    except: pass
    finally: conn.close()
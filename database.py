import sqlite3
import pandas as pd
import streamlit as st
import os

from config import DEFAULT_CATEGORIES, get_flat_categories

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "ledger.db")

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            item TEXT,
            amount INTEGER,
            category TEXT,
            spender TEXT DEFAULT '공동',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS fixed_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            spender TEXT DEFAULT '공동',
            payment_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            amount INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            is_default INTEGER DEFAULT 0
        )
    ''')
    
    # [마이그레이션] 기존 DB에 type(소비성향) 컬럼이 없다면 추가
    try:
        c.execute("ALTER TABLE categories ADD COLUMN type TEXT")
    except sqlite3.OperationalError:
        pass # 이미 컬럼이 존재하면 넘어감
    
    conn.commit()
    conn.close()
    
    seed_categories()

def seed_categories():
    """초기 카테고리 데이터를 소비성향과 함께 삽입 및 업데이트합니다."""
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM categories")
        count = c.fetchone()[0]
        
        # 카테고리가 아예 없으면 신규 생성
        if count == 0:
            for cat_type, cat_list in DEFAULT_CATEGORIES.items():
                for cat in cat_list:
                    c.execute("INSERT OR IGNORE INTO categories (name, is_default, type) VALUES (?, 1, ?)", (cat, cat_type))
        else:
            # 카테고리는 있지만 type이 비어있는 과거 데이터들 업데이트
            for cat_type, cat_list in DEFAULT_CATEGORIES.items():
                for cat in cat_list:
                    c.execute("UPDATE categories SET type = ? WHERE name = ? AND type IS NULL", (cat_type, cat))
                    
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"초기 카테고리 설정 중 오류 발생: {e}")

# --- 카테고리 관리 함수 ---
def get_categories():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name FROM categories ORDER BY name", conn)
        return df['name'].tolist()
    except: return []
    finally: conn.close()

# [신규] 카테고리별 소비성향을 딕셔너리로 반환
def get_category_mapping():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name, type FROM categories", conn)
        return {row['name']: (row['type'] if row['type'] else '미분류') for _, row in df.iterrows()}
    except: return {}
    finally: conn.close()

# [수정] 카테고리 추가 시 type(소비성향)도 함께 받음
def add_category(new_category, cat_type):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (new_category, cat_type))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        st.warning("이미 존재하는 카테고리입니다.")
        return False
    finally: conn.close()

def delete_category_safe(category_name):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE expenses SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("UPDATE fixed_expenses SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("UPDATE budgets SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("DELETE FROM categories WHERE name = ?", (category_name,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False
    finally: conn.close()

# --- 기타 기존 함수 유지 ---
def insert_expense(data_list):
    conn = get_connection()
    c = conn.cursor()
    try:
        for entry in data_list:
            spender = entry.get('spender', '공동')
            c.execute('''INSERT INTO expenses (date, item, amount, category, spender)
                         VALUES (?, ?, ?, ?, ?)''', (entry['date'], entry['item'], entry['amount'], entry['category'], spender))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def load_data(month_str=None, spender_filter=None):
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
        return pd.read_sql(query, conn, params=params)
    except: return pd.DataFrame()
    finally: conn.close()

def get_available_months():
    conn = get_connection()
    try:
        query = "SELECT DISTINCT substr(date, 1, 7) as month FROM expenses ORDER BY month DESC"
        return pd.read_sql(query, conn)['month'].tolist()
    except: return []
    finally: conn.close()

def delete_expense(expense_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
        conn.commit()
    except: pass
    finally: conn.close()

def update_expense(expense_id, column, new_value):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"UPDATE expenses SET {column} = ? WHERE id = ?", (new_value, int(expense_id)))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

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
    try: return pd.read_sql("SELECT * FROM budgets", conn)
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
    try: return pd.read_sql("SELECT * FROM fixed_expenses ORDER BY payment_day ASC", conn)
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
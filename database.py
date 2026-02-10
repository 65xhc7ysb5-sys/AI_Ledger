import sqlite3
import pandas as pd
import streamlit as st
import os

# [핵심 수정] 현재 파일(database.py)의 위치를 기준으로 절대 경로 설정
# 이렇게 해야 home.py에서 실행하든 pages/dashboard.py에서 실행하든 같은 DB를 봅니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "ledger.db")

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # 1. 일반 지출
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            item TEXT,
            amount INTEGER,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. 고정 지출
    c.execute('''
        CREATE TABLE IF NOT EXISTS fixed_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            payment_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. 예산
    c.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            amount INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

# --- 일반 지출 함수 ---
def insert_expense(data_list):
    conn = get_connection()
    c = conn.cursor()
    try:
        for entry in data_list:
            c.execute('''
                INSERT INTO expenses (date, item, amount, category)
                VALUES (?, ?, ?, ?)
            ''', (entry['date'], entry['item'], entry['amount'], entry['category']))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ DB 저장 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

def load_data(month_str=None):
    conn = get_connection()
    try:
        if month_str and month_str != "전체 기간":
            query = "SELECT * FROM expenses WHERE date LIKE ? ORDER BY date DESC"
            df = pd.read_sql(query, conn, params=(f"{month_str}%",))
        else:
            df = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC", conn)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def get_available_months():
    conn = get_connection()
    try:
        query = "SELECT DISTINCT substr(date, 1, 7) as month FROM expenses ORDER BY month DESC"
        df = pd.read_sql(query, conn)
        return df['month'].tolist()
    except Exception as e:
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
        st.error(f"❌ 삭제 중 오류 발생: {e}")
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
        st.error(f"❌ 수정 중 오류 발생: {e}")
        return False
    finally:
        conn.close()

# --- 고정 지출 함수 ---
def save_fixed_expense(item, amount, category, payment_day):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO fixed_expenses (item, amount, category, payment_day)
            VALUES (?, ?, ?, ?)
        ''', (item, amount, category, payment_day))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"고정 지출 저장 실패: {e}")
        return False
    finally:
        conn.close()

def get_fixed_expenses():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM fixed_expenses ORDER BY payment_day ASC", conn)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def delete_fixed_expense(fixed_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM fixed_expenses WHERE id = ?", (int(fixed_id),))
        conn.commit()
    except Exception as e:
        st.error(f"고정 지출 삭제 실패: {e}")
    finally:
        conn.close()

# --- 예산 관련 함수 ---
def save_budget(category, amount):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR REPLACE INTO budgets (category, amount)
            VALUES (?, ?)
        ''', (category, amount))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"예산 저장 실패: {e}")
        return False
    finally:
        conn.close()

def get_budgets():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM budgets", conn)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def delete_budget(category):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM budgets WHERE category = ?", (category,))
        conn.commit()
    except Exception as e:
        st.error(f"예산 삭제 실패: {e}")
    finally:
        conn.close()
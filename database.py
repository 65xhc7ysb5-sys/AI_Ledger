import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = "ledger.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

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

# [수정됨] 특정 월(month_str)을 받아서 필터링하는 기능 추가
def load_data(month_str=None):
    """
    month_str: '2026-02' 형태의 문자열. None이면 전체 데이터 조회.
    """
    conn = get_connection()
    try:
        if month_str and month_str != "전체 기간":
            # SQLite의 LIKE를 사용하여 '2026-02%' 패턴으로 검색
            query = "SELECT * FROM expenses WHERE date LIKE ? ORDER BY date DESC"
            df = pd.read_sql(query, conn, params=(f"{month_str}%",))
        else:
            df = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC", conn)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

# [신규 추가] 데이터가 존재하는 '연-월' 목록 가져오기 (필터용)
def get_available_months():
    conn = get_connection()
    try:
        # 날짜(date)에서 앞 7자리(YYYY-MM)만 잘라서 중복 제거하고 가져옴
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
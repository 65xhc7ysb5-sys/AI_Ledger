import sqlite3
import pandas as pd
import streamlit as st
import os

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

def load_data():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC", conn)
        return df
    except Exception as e:
        return pd.DataFrame()
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

# [✨ 새로 추가된 함수] 데이터 수정
def update_expense(expense_id, column, new_value):
    """
    expense_id: 수정할 데이터의 ID
    column: 수정할 컬럼명 (예: 'amount', 'item', 'category')
    new_value: 새로운 값
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 동적 쿼리 사용 (컬럼명은 매개변수로 바인딩되지 않으므로 f-string 사용)
        # 보안: column 변수는 코드 내부에서만 제어하므로 SQL Injection 위험 낮음
        query = f"UPDATE expenses SET {column} = ? WHERE id = ?"
        c.execute(query, (new_value, int(expense_id)))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 수정 중 오류 발생: {e}")
        return False
    finally:
        conn.close()
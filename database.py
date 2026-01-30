import sqlite3
import pandas as pd
import streamlit as st
import os

DB_NAME = "ledger.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_db():
    """테이블이 없으면 새로 생성"""
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
    """데이터 저장 (성공/실패 메시지 강화)"""
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
        st.error(f"❌ DB 저장 중 오류 발생: {e}") # 에러 메시지 화면 출력
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
    """데이터 삭제"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # [수정 포인트] id를 반드시 정수(int)로 변환해야 삭제가 작동함
        c.execute("DELETE FROM expenses WHERE id = ?", (int(expense_id),))
        conn.commit()
    except Exception as e:
        st.error(f"❌ 삭제 중 오류 발생: {e}")
    finally:
        conn.close()
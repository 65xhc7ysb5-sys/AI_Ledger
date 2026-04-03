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

    # [마이그레이션] 기존 DB에 type 컬럼이 없다면 추가
    try:
        c.execute("ALTER TABLE categories ADD COLUMN type TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 존재하면 넘어감

    c.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

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

        if count == 0:
            for cat_type, cat_list in DEFAULT_CATEGORIES.items():
                for cat in cat_list:
                    c.execute(
                        "INSERT OR IGNORE INTO categories (name, is_default, type) VALUES (?, 1, ?)",
                        (cat, cat_type),
                    )
        else:
            for cat_type, cat_list in DEFAULT_CATEGORIES.items():
                for cat in cat_list:
                    c.execute(
                        "UPDATE categories SET type = ? WHERE name = ? AND type IS NULL",
                        (cat_type, cat),
                    )

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"초기 카테고리 설정 중 오류 발생: {e}")


# --- 카테고리 관리 함수 ---

def get_categories():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name FROM categories ORDER BY name", conn)
        return df["name"].tolist()
    except:
        return []
    finally:
        conn.close()


def get_category_mapping():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT name, type FROM categories", conn)
        return {row["name"]: (row["type"] if row["type"] else "미분류") for _, row in df.iterrows()}
    except:
        return {}
    finally:
        conn.close()


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
    finally:
        conn.close()


def delete_category_safe(category_name):
    """카테고리 삭제 시 expenses·fixed_expenses·budgets 레코드도 정리합니다."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE expenses SET category = '미분류' WHERE category = ?", (category_name,))
        c.execute("UPDATE fixed_expenses SET category = '미분류' WHERE category = ?", (category_name,))
        # ★ budgets에서도 해당 카테고리 행 삭제 (미분류로 이동 대신 제거)
        c.execute("DELETE FROM budgets WHERE category = ?", (category_name,))
        c.execute("DELETE FROM categories WHERE name = ?", (category_name,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False
    finally:
        conn.close()


# --- 지출 함수 ---

def insert_expense(data_list):
    conn = get_connection()
    c = conn.cursor()
    try:
        for entry in data_list:
            spender = entry.get("spender", "공동")
            c.execute(
                "INSERT INTO expenses (date, item, amount, category, spender) VALUES (?, ?, ?, ?, ?)",
                (entry["date"], entry["item"], entry["amount"], entry["category"], spender),
            )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


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
    except:
        return pd.DataFrame()
    finally:
        conn.close()


def get_available_months():
    conn = get_connection()
    try:
        query = "SELECT DISTINCT substr(date, 1, 7) as month FROM expenses ORDER BY month DESC"
        return pd.read_sql(query, conn)["month"].tolist()
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
    except:
        pass
    finally:
        conn.close()


def update_expense(expense_id, column, new_value):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"UPDATE expenses SET {column} = ? WHERE id = ?", (new_value, int(expense_id)))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


# --- 예산 함수 ---

def save_budget(category, amount):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO budgets (category, amount) VALUES (?, ?)",
            (category, amount),
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def get_budgets():
    """
    ★ categories 테이블에 존재하는 유효한 카테고리의 예산만 반환.

    INNER JOIN으로 고아 레코드(카테고리가 삭제됐지만 budgets에 남은 행)를
    자동으로 배제합니다. 카테고리를 추가·삭제해도 합계가 항상 정확합니다.
    """
    conn = get_connection()
    try:
        return pd.read_sql(
            """SELECT b.category, b.amount
               FROM budgets b
               INNER JOIN categories c ON b.category = c.name
               ORDER BY b.category""",
            conn,
        )
    except:
        return pd.DataFrame()
    finally:
        conn.close()


def delete_budget(category):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM budgets WHERE category = ?", (category,))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def clear_all_budgets():
    """
    ★ budgets 테이블 전체 초기화.

    "이 기준으로 예산 자동 세팅" / "추천 예산 저장" 버튼 클릭 전에 호출해
    이전 세팅의 잔존 레코드(예: 여행)가 합계를 오염시키는 것을 방지합니다.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM budgets")
        conn.commit()
    except:
        pass
    finally:
        conn.close()


# --- 고정 지출 함수 ---

def save_fixed_expense(item, amount, category, payment_day, spender="공동"):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO fixed_expenses (item, amount, category, spender, payment_day) VALUES (?, ?, ?, ?, ?)",
            (item, amount, category, spender, payment_day),
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()


def get_fixed_expenses():
    conn = get_connection()
    try:
        return pd.read_sql("SELECT * FROM fixed_expenses ORDER BY payment_day ASC", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()


def delete_fixed_expense(fixed_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM fixed_expenses WHERE id = ?", (int(fixed_id),))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


# --- 앱 설정 함수 ---

def save_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def get_setting(key, default_val=None):
    conn = get_connection()
    try:
        df = pd.read_sql(
            "SELECT value FROM app_settings WHERE key = ?", conn, params=(key,)
        )
        if not df.empty:
            return df.iloc[0]["value"]
    except:
        pass
    finally:
        conn.close()
    return default_val
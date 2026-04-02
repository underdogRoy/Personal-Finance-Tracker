import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                source TEXT DEFAULT 'csv',
                llm_categorized INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON transactions(date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON transactions(category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON transactions(type)')
        conn.commit()
    finally:
        conn.close()


def insert_transaction(date, description, category, amount, type_, source='csv', llm_categorized=0):
    conn = get_connection()
    try:
        cursor = conn.execute(
            '''INSERT INTO transactions (date, description, category, amount, type, source, llm_categorized)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (date, description, category, float(amount), type_, source, int(llm_categorized))
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_transactions(filters=None):
    conn = get_connection()
    try:
        query = 'SELECT * FROM transactions WHERE 1=1'
        params = []

        if filters:
            if filters.get('start_date'):
                query += ' AND date >= ?'
                params.append(filters['start_date'])
            if filters.get('end_date'):
                query += ' AND date <= ?'
                params.append(filters['end_date'])
            if filters.get('category'):
                query += ' AND category = ?'
                params.append(filters['category'])
            if filters.get('type'):
                query += ' AND type = ?'
                params.append(filters['type'])

        query += ' ORDER BY date DESC, id DESC'
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_summary_stats():
    conn = get_connection()
    try:
        row = conn.execute('''
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0) AS total_expense,
                COUNT(*) AS transaction_count
            FROM transactions
        ''').fetchone()

        total_income = row['total_income']
        total_expense = row['total_expense']
        net_savings = total_income - total_expense

        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_savings': net_savings,
            'transaction_count': row['transaction_count']
        }
    finally:
        conn.close()


def get_spending_by_category():
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE type = 'Expense'
            GROUP BY category
            ORDER BY total DESC
        ''').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_monthly_spending():
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT
                strftime('%Y-%m', date) AS month,
                SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END) AS total_expense,
                SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END) AS total_income
            FROM transactions
            GROUP BY month
            ORDER BY month ASC
        ''').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def is_db_empty():
    conn = get_connection()
    try:
        row = conn.execute('SELECT COUNT(*) AS cnt FROM transactions').fetchone()
        return row['cnt'] == 0
    finally:
        conn.close()


def delete_transaction(id_):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM transactions WHERE id = ?', (id_,))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def update_transaction_category(id_, category, llm_categorized=1):
    conn = get_connection()
    try:
        conn.execute(
            'UPDATE transactions SET category = ?, llm_categorized = ? WHERE id = ?',
            (category, int(llm_categorized), id_)
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_transaction_by_id(id_):
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM transactions WHERE id = ?', (id_,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

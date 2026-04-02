import os
import io
import csv
import json
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, g
)
from dotenv import load_dotenv

load_dotenv()

# Optional anthropic import
try:
    import anthropic as _anthropic_lib
    ANTHROPIC_PACKAGE_AVAILABLE = True
except ImportError:
    ANTHROPIC_PACKAGE_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from database import (
    init_db, insert_transaction, get_all_transactions, get_summary_stats,
    get_spending_by_category, get_monthly_spending, is_db_empty,
    delete_transaction, update_transaction_category, get_transaction_by_id
)
from categorizer import categorize_transaction, CATEGORIES
from insights import generate_insights

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
anthropic_client = None
if ANTHROPIC_PACKAGE_AVAILABLE and ANTHROPIC_API_KEY:
    try:
        anthropic_client = _anthropic_lib.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        anthropic_client = None

SAMPLE_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Personal_Finance_Dataset.csv')

# ---------------------------------------------------------------------------
# DB init + auto-load
# ---------------------------------------------------------------------------
init_db()

_auto_loaded = False


def auto_load_sample_data():
    """Load the bundled CSV using its existing Category column (no LLM calls)."""
    if not os.path.exists(SAMPLE_CSV_PATH):
        return 0

    loaded = 0
    if PANDAS_AVAILABLE:
        try:
            df = pd.read_csv(SAMPLE_CSV_PATH)
            df.columns = [c.strip() for c in df.columns]
            for _, row in df.iterrows():
                try:
                    date_val = str(row.get('Date', '')).strip()
                    desc = str(row.get('Transaction Description', '')).strip()
                    category = str(row.get('Category', 'Other')).strip()
                    amount = float(row.get('Amount', 0))
                    type_ = str(row.get('Type', 'Expense')).strip()
                    if not date_val or not desc:
                        continue
                    insert_transaction(date_val, desc, category, amount, type_, source='sample', llm_categorized=0)
                    loaded += 1
                except Exception:
                    continue
        except Exception:
            pass
    else:
        try:
            with open(SAMPLE_CSV_PATH, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        date_val = str(row.get('Date', '')).strip()
                        desc = str(row.get('Transaction Description', '')).strip()
                        category = str(row.get('Category', 'Other')).strip()
                        amount = float(row.get('Amount', 0))
                        type_ = str(row.get('Type', 'Expense')).strip()
                        if not date_val or not desc:
                            continue
                        insert_transaction(date_val, desc, category, amount, type_, source='sample', llm_categorized=0)
                        loaded += 1
                    except Exception:
                        continue
        except Exception:
            pass
    return loaded


@app.before_request
def check_auto_load():
    global _auto_loaded
    if not _auto_loaded:
        _auto_loaded = True
        if is_db_empty():
            auto_load_sample_data()


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        'api_key_configured': bool(ANTHROPIC_API_KEY),
        'categories': CATEGORIES,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    stats = get_summary_stats()
    spending_by_cat = get_spending_by_category()
    monthly_data = get_monthly_spending()
    return render_template('index.html', stats=stats,
                           spending_by_category=spending_by_cat,
                           monthly_data=monthly_data)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        use_ai = request.form.get('use_ai') == 'on' and anthropic_client is not None
        client = anthropic_client if use_ai else None

        csv_text = None

        # File upload
        if 'csv_file' in request.files and request.files['csv_file'].filename:
            file = request.files['csv_file']
            try:
                csv_text = file.read().decode('utf-8', errors='replace')
            except Exception as e:
                flash(f'Error reading file: {e}', 'danger')
                return redirect(url_for('upload'))

        # Paste CSV
        elif request.form.get('csv_text', '').strip():
            csv_text = request.form['csv_text'].strip()

        if not csv_text:
            flash('Please provide a CSV file or paste CSV text.', 'warning')
            return redirect(url_for('upload'))

        # Parse CSV
        loaded = 0
        errors = 0
        try:
            if PANDAS_AVAILABLE:
                df = pd.read_csv(io.StringIO(csv_text))
                df.columns = [c.strip() for c in df.columns]

                # Detect columns (flexible)
                col_date = _find_col(df.columns, ['date'])
                col_desc = _find_col(df.columns, ['transaction description', 'description', 'desc', 'memo', 'narration'])
                col_amount = _find_col(df.columns, ['amount', 'debit', 'credit', 'value'])
                col_type = _find_col(df.columns, ['type', 'transaction type'])
                col_category = _find_col(df.columns, ['category'])

                if not col_date or not col_desc or not col_amount:
                    flash('CSV must have at least Date, Description, and Amount columns.', 'danger')
                    return redirect(url_for('upload'))

                for _, row in df.iterrows():
                    try:
                        date_val = str(row[col_date]).strip()
                        desc = str(row[col_desc]).strip()
                        amount = abs(float(str(row[col_amount]).replace(',', '')))
                        type_ = str(row[col_type]).strip() if col_type else _infer_type(row[col_amount])
                        type_ = type_ if type_ in ('Income', 'Expense') else 'Expense'

                        if col_category:
                            category = str(row[col_category]).strip()
                            llm_used = False
                        else:
                            category, llm_used = categorize_transaction(desc, amount, type_, client)

                        insert_transaction(date_val, desc, category, amount, type_, source='upload', llm_categorized=int(llm_used))
                        loaded += 1
                    except Exception:
                        errors += 1
            else:
                reader = csv.DictReader(io.StringIO(csv_text))
                fieldnames = [f.strip() for f in (reader.fieldnames or [])]
                col_date = _find_col(fieldnames, ['date'])
                col_desc = _find_col(fieldnames, ['transaction description', 'description', 'desc', 'memo'])
                col_amount = _find_col(fieldnames, ['amount', 'debit', 'credit'])
                col_type = _find_col(fieldnames, ['type', 'transaction type'])
                col_category = _find_col(fieldnames, ['category'])

                if not col_date or not col_desc or not col_amount:
                    flash('CSV must have at least Date, Description, and Amount columns.', 'danger')
                    return redirect(url_for('upload'))

                for row in reader:
                    try:
                        date_val = str(row.get(col_date, '')).strip()
                        desc = str(row.get(col_desc, '')).strip()
                        amount = abs(float(str(row.get(col_amount, '0')).replace(',', '')))
                        type_ = str(row.get(col_type, 'Expense')).strip()
                        type_ = type_ if type_ in ('Income', 'Expense') else 'Expense'

                        if col_category:
                            category = str(row.get(col_category, 'Other')).strip()
                            llm_used = False
                        else:
                            category, llm_used = categorize_transaction(desc, amount, type_, client)

                        insert_transaction(date_val, desc, category, amount, type_, source='upload', llm_categorized=int(llm_used))
                        loaded += 1
                    except Exception:
                        errors += 1

            msg = f'Successfully imported {loaded} transaction(s).'
            if errors:
                msg += f' {errors} row(s) skipped due to errors.'
            flash(msg, 'success')
        except Exception as e:
            flash(f'Failed to parse CSV: {e}', 'danger')

        return redirect(url_for('index'))

    return render_template('upload.html')


@app.route('/transactions')
def transactions():
    page = int(request.args.get('page', 1))
    per_page = 50
    filters = {
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'category': request.args.get('category', ''),
        'type': request.args.get('type', ''),
    }
    # Remove empty filters
    active_filters = {k: v for k, v in filters.items() if v}
    all_txns = get_all_transactions(active_filters if active_filters else None)

    total = len(all_txns)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    txns = all_txns[start:start + per_page]

    return render_template('transactions.html',
                           transactions=txns,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           filters=filters)


@app.route('/transactions/add', methods=['POST'])
def add_transaction():
    try:
        date_val = request.form['date'].strip()
        desc = request.form['description'].strip()
        amount = abs(float(request.form['amount']))
        type_ = request.form['type'].strip()

        if not date_val or not desc or not amount or type_ not in ('Income', 'Expense'):
            flash('Please fill in all fields correctly.', 'warning')
            return redirect(url_for('transactions'))

        category, llm_used = categorize_transaction(desc, amount, type_, anthropic_client)
        insert_transaction(date_val, desc, category, amount, type_, source='manual', llm_categorized=int(llm_used))
        flash(f'Transaction added successfully (category: {category}).', 'success')
    except Exception as e:
        flash(f'Error adding transaction: {e}', 'danger')

    return redirect(url_for('transactions'))


@app.route('/transactions/<int:id>/delete', methods=['POST'])
def delete_txn(id):
    try:
        deleted = delete_transaction(id)
        if deleted:
            flash('Transaction deleted.', 'success')
        else:
            flash('Transaction not found.', 'warning')
    except Exception as e:
        flash(f'Error deleting transaction: {e}', 'danger')
    return redirect(url_for('transactions'))


@app.route('/transactions/<int:id>/recategorize', methods=['POST'])
def recategorize_txn(id):
    txn = get_transaction_by_id(id)
    if not txn:
        return jsonify({'error': 'Transaction not found'}), 404

    if not anthropic_client:
        return jsonify({'error': 'No API key configured'}), 400

    try:
        from categorizer import llm_categorize
        category = llm_categorize(txn['description'], txn['amount'], txn['type'], anthropic_client)
        update_transaction_category(id, category, llm_categorized=1)
        return jsonify({'success': True, 'category': category})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insights')
def insights():
    stats = get_summary_stats()
    spending_by_cat = get_spending_by_category()
    monthly_data = get_monthly_spending()
    insights_html = None

    if anthropic_client:
        insights_html = generate_insights(spending_by_cat, monthly_data, stats, anthropic_client)

    return render_template('insights.html',
                           stats=stats,
                           insights_html=insights_html)


@app.route('/api/chart-data')
def chart_data():
    spending_by_cat = get_spending_by_category()
    monthly_data = get_monthly_spending()
    return jsonify({
        'spending_by_category': spending_by_cat,
        'monthly_data': monthly_data
    })


@app.route('/load-sample-data')
def load_sample_data():
    """Demo route: reload the bundled CSV with rule-based categorization."""
    count = auto_load_sample_data()
    if count:
        flash(f'Loaded {count} sample transactions.', 'success')
    else:
        flash('Sample data already loaded or file not found.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_col(columns, candidates):
    """Case-insensitive column name finder."""
    lower_cols = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]
    return None


def _infer_type(amount_val):
    try:
        return 'Income' if float(str(amount_val).replace(',', '')) > 0 else 'Expense'
    except Exception:
        return 'Expense'


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5000)

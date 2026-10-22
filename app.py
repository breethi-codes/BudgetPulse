from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import math
import calendar
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-secret-key')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['DATABASE'] = os.path.join(BASE_DIR, 'instance', 'budget.db')

CATEGORIES = {
    'Food': 'Food & Dining',
    'Transport': 'Transport',
    'Utilities': 'Utilities & Bills',
    'Entertainment': 'Entertainment',
    'Shopping': 'Shopping',
    'Other': 'Other',
}

MAX_AMOUNT = 10000000   # 1 crore
MAX_TITLE_LENGTH = 100


def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL DEFAULT 0.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()


init_db()

def clean_month(month_text):
    """Return the month as 'YYYY-MM'. If the text is invalid, return the current month."""
    try:
        parsed = datetime.strptime(month_text, '%Y-%m')
    except (ValueError, TypeError):
        return datetime.now().strftime('%Y-%m')
    return parsed.date().isoformat()[:7]


def clean_date(date_text):
    """Return the date as 'YYYY-MM-DD'. If the date is invalid, return None."""
    try:
        parsed = datetime.strptime(date_text, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
    return parsed.date().isoformat()


def read_amount(amount_text):
    """Convert text to a number with 2 decimals. Return None if it is not a normal number."""
    try:
        amount = float(amount_text)
    except (ValueError, TypeError):
        return None
    if math.isnan(amount) or math.isinf(amount):
        return None
    return round(amount, 2)


def get_month_range(month_text):
    """Return the first and last date of a month, like ('2026-10-01', '2026-10-31')."""
    year = int(month_text[:4])
    month = int(month_text[5:7])
    last_day = calendar.monthrange(year, month)[1]
    first_date = f'{month_text}-01'
    last_date = f'{month_text}-{last_day:02d}'
    return first_date, last_date

@app.route('/')
def index():
    current_month = datetime.now().strftime('%Y-%m')
    selected_month = clean_month(request.args.get('month', current_month))
    month_start, month_end = get_month_range(selected_month)

    monthly_budget = 0.0
    total_spent = 0.0
    expenses = []
    category_summary = []

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Budget of the selected month
        cursor.execute('SELECT amount FROM budget WHERE month = ?', (selected_month,))
        budget_row = cursor.fetchone()
        if budget_row:
            monthly_budget = float(budget_row['amount'])

        # All expenses of the selected month (newest first)
        cursor.execute(
            'SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC',
            (month_start, month_end))
        expenses = cursor.fetchall()

        # Total spent in the selected month
        cursor.execute(
            'SELECT SUM(amount) AS total_spent FROM expenses WHERE date BETWEEN ? AND ?',
            (month_start, month_end))
        sum_row = cursor.fetchone()
        if sum_row['total_spent'] is not None:
            total_spent = round(float(sum_row['total_spent']), 2)

        # Category-wise total (biggest first)
        cursor.execute(
            'SELECT category, SUM(amount) AS total FROM expenses '
            'WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY total DESC',
            (month_start, month_end))
        category_summary = cursor.fetchall()
    except sqlite3.Error:
        flash('Could not read data from the database.', 'error')
    finally:
        if conn is not None:
            conn.close()

    
    cat_labels = [row['category'] for row in category_summary]
    cat_totals = [round(float(row['total']), 2) for row in category_summary]

    # Budget calculations
    budget_is_set = monthly_budget > 0
    remaining_budget = round(monthly_budget - total_spent, 2)
    percent_used = 0
    warning_80 = False
    exceeded_100 = False

    if budget_is_set:
        percent_used = round(total_spent / monthly_budget * 100, 1)
        if total_spent >= monthly_budget:
            exceeded_100 = True
        elif total_spent >= round(monthly_budget * 0.8, 2):
            warning_80 = True

    
    if selected_month == current_month:
        default_date = datetime.now().strftime('%Y-%m-%d')
    else:
        default_date = f'{selected_month}-01'

    return render_template('index.html',
                           selected_month=selected_month,
                           monthly_budget=monthly_budget,
                           budget_is_set=budget_is_set,
                           total_spent=total_spent,
                           remaining_budget=remaining_budget,
                           percent_used=percent_used,
                           expenses=expenses,
                           category_summary=category_summary,
                           cat_labels=cat_labels,
                           cat_totals=cat_totals,
                           warning_80=warning_80,
                           exceeded_100=exceeded_100,
                           categories=CATEGORIES,
                           default_date=default_date)


@app.route('/set_budget', methods=['POST'])
def set_budget():
    selected_month = clean_month(request.form.get('month'))
    budget_amount = read_amount(request.form.get('budget_amount', ''))

    if budget_amount is None:
        flash('Invalid budget amount.', 'error')
    elif budget_amount < 0:
        flash('Budget cannot be negative.', 'error')
    elif budget_amount > MAX_AMOUNT:
        flash('Budget is too large.', 'error')
    else:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM budget WHERE month = ?', (selected_month,))
            if cursor.fetchone():
                cursor.execute('UPDATE budget SET amount = ? WHERE month = ?',
                               (budget_amount, selected_month))
            else:
                cursor.execute('INSERT INTO budget (month, amount) VALUES (?, ?)',
                               (selected_month, budget_amount))
            conn.commit()
            flash('Monthly budget updated successfully!', 'success')
        except sqlite3.Error:
            flash('Database error. The budget was not saved.', 'error')
        finally:
            if conn is not None:
                conn.close()

    return redirect(url_for('index', month=selected_month))


@app.route('/add_expense', methods=['POST'])
def add_expense():
    selected_month = clean_month(request.form.get('month'))
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    expense_date = clean_date(request.form.get('date', '').strip())
    amount = read_amount(request.form.get('amount', ''))

    month_to_show = selected_month

    if not title:
        flash('Please enter the expense title.', 'error')
    elif len(title) > MAX_TITLE_LENGTH:
        flash(f'Title must be {MAX_TITLE_LENGTH} characters or less.', 'error')
    elif category not in CATEGORIES:
        flash('Please select a valid category.', 'error')
    elif expense_date is None:
        flash('Please enter a valid date.', 'error')
    elif amount is None or amount <= 0:
        flash('Amount must be a number greater than zero.', 'error')
    elif amount > MAX_AMOUNT:
        flash('Amount is too large.', 'error')
    else:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO expenses (title, amount, category, date) VALUES (?, ?, ?, ?)',
                (title, amount, category, expense_date))
            conn.commit()
            flash('Expense added successfully!', 'success')
            # Show the month of the new expense, so the user can see it
            month_to_show = expense_date[:7]
        except sqlite3.Error:
            flash('Database error. The expense was not saved.', 'error')
        finally:
            if conn is not None:
                conn.close()

    return redirect(url_for('index', month=month_to_show))


@app.route('/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    month_to_show = datetime.now().strftime('%Y-%m')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT date FROM expenses WHERE id = ?', (expense_id,))
        expense_row = cursor.fetchone()

        if expense_row is None:
            flash('Expense not found.', 'error')
        else:
            month_to_show = expense_row['date'][:7]
            cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
            conn.commit()
            flash('Expense deleted successfully.', 'success')
    except sqlite3.Error:
        flash('Database error. The expense was not deleted.', 'error')
    finally:
        if conn is not None:
            conn.close()

    return redirect(url_for('index', month=month_to_show))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
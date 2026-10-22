import re
import pytest
from app import app, init_db, get_db_connection


@pytest.fixture
def client(tmp_path):
    """Test client that uses a temporary database (your real budget.db is never touched)."""
    old_database = app.config['DATABASE']
    app.config['TESTING'] = True
    app.config['DATABASE'] = str(tmp_path / 'test_budget.db')
    init_db()

    with app.test_client() as test_client:
        yield test_client

    app.config['DATABASE'] = old_database


def page_text(response):
    return response.get_data(as_text=True)


def set_budget(client, month, amount):
    return client.post('/set_budget',
                       data={'month': month, 'budget_amount': amount},
                       follow_redirects=True)


def add_expense(client, month='2026-10', title='Test', amount='100',
                category='Food', date='2026-10-15'):
    return client.post('/add_expense',
                       data={'month': month, 'title': title, 'amount': amount,
                             'category': category, 'date': date},
                       follow_redirects=True)


def card_value(html, heading):
    """Read the number shown under a card heading, like 'Total Spent'."""
    pattern = rf'<h3>{heading}</h3>\s*<p class="[^"]*">\s*(.*?)\s*</p>'
    match = re.search(pattern, html, re.S)
    return match.group(1) if match else None


def count_expenses():
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) FROM expenses').fetchone()[0]
    conn.close()
    return count


def test_homepage_loads(client):
    response = client.get('/')
    html = page_text(response)
    assert response.status_code == 200
    assert 'Expense Dashboard' in html
    assert 'BudgetPulse' in html


def test_empty_month_shows_empty_messages(client):
    html = page_text(client.get('/?month=2026-10'))
    assert 'No transactions found.' in html
    assert 'No expenses recorded for this month yet.' in html
    assert card_value(html, 'Total Spent') == '₹0.00'


def test_invalid_month_in_url_does_not_crash(client):
    assert client.get('/?month=abc').status_code == 200
    assert client.get('/?month=2026-13').status_code == 200


def test_short_month_is_made_standard(client):
    html = page_text(client.get('/?month=2026-1'))
    assert 'Transaction History for 2026-01' in html


def test_set_budget(client):
    html = page_text(set_budget(client, '2026-10', '10000'))
    assert 'Monthly budget updated successfully!' in html
    assert card_value(html, 'Monthly Budget') == '₹10000.00'


def test_update_budget_changes_same_month(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(set_budget(client, '2026-10', '2500'))
    assert card_value(html, 'Monthly Budget') == '₹2500.00'


def test_budget_is_separate_for_each_month(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(client.get('/?month=2026-11'))
    assert card_value(html, 'Monthly Budget') == '₹0.00'


def test_negative_budget_rejected(client):
    html = page_text(set_budget(client, '2026-10', '-500'))
    assert 'Budget cannot be negative.' in html
    assert card_value(html, 'Monthly Budget') == '₹0.00'


@pytest.mark.parametrize('bad_value', ['abc', '', 'nan', 'inf'])
def test_invalid_budget_rejected(client, bad_value):
    html = page_text(set_budget(client, '2026-10', bad_value))
    assert 'Invalid budget amount.' in html


def test_add_expense(client):
    html = page_text(add_expense(client, title='Grocery', amount='450.50'))
    assert 'Expense added successfully!' in html
    assert 'Grocery' in html
    assert card_value(html, 'Total Spent') == '₹450.50'
    assert count_expenses() == 1


def test_empty_title_rejected(client):
    html = page_text(add_expense(client, title='   '))
    assert 'Please enter the expense title.' in html
    assert count_expenses() == 0


@pytest.mark.parametrize('bad_amount', ['0', '-5', 'abc', '', 'nan', 'inf'])
def test_bad_amount_rejected(client, bad_amount):
    html = page_text(add_expense(client, amount=bad_amount))
    assert 'Amount must be a number greater than zero.' in html
    assert count_expenses() == 0


def test_invalid_date_rejected(client):
    html = page_text(add_expense(client, date='abc'))
    assert 'Please enter a valid date.' in html
    assert count_expenses() == 0


def test_invalid_category_rejected(client):
    html = page_text(add_expense(client, category='Hacking'))
    assert 'Please select a valid category.' in html
    assert count_expenses() == 0


def test_expense_of_another_month_shows_that_month(client):
    html = page_text(add_expense(client, month='2026-10', date='2026-11-05'))
    assert 'Transaction History for 2026-11' in html
    assert card_value(html, 'Total Spent') == '₹100.00'


def test_html_in_title_is_escaped(client):
    html = page_text(add_expense(client, title='<script>alert(1)</script>'))
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html



def test_month_filter_uses_only_selected_month(client):
    add_expense(client, amount='1', date='2026-09-30')
    add_expense(client, amount='2', date='2026-10-01')
    add_expense(client, amount='4', date='2026-10-31')
    add_expense(client, amount='8', date='2026-11-01')

    october = page_text(client.get('/?month=2026-10'))
    assert card_value(october, 'Total Spent') == '₹6.00'

    november = page_text(client.get('/?month=2026-11'))
    assert card_value(november, 'Total Spent') == '₹8.00'


def test_remaining_budget_is_budget_minus_spent(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(add_expense(client, amount='300'))
    assert card_value(html, 'Total Spent') == '₹300.00'
    assert card_value(html, 'Remaining Budget') == '₹700.00'


def test_category_totals(client):
    add_expense(client, amount='100', category='Food')
    add_expense(client, amount='50', category='Food')
    html = page_text(add_expense(client, amount='25', category='Transport'))
    assert re.search(r'cat-name">Food</span>\s*<span class="cat-amount">₹150.00', html)
    assert re.search(r'cat-name">Transport</span>\s*<span class="cat-amount">₹25.00', html)


def test_chart_data_attributes_are_readable_by_javascript(client):
    html = page_text(add_expense(client, amount='500', category='Food'))
    assert "data-labels='[\"Food\"]'" in html
    assert "data-totals='[500.0]'" in html


def test_no_warning_below_80_percent(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(add_expense(client, amount='799.99'))
    assert '80% or more' not in html
    assert 'Budget limit reached' not in html


def test_warning_at_exactly_80_percent(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(add_expense(client, amount='800'))
    assert '80% or more' in html
    assert 'Budget limit reached' not in html


def test_limit_message_at_exactly_100_percent(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(add_expense(client, amount='1000'))
    assert 'Budget limit reached' in html
    assert '80% or more' not in html


def test_limit_message_above_100_percent(client):
    set_budget(client, '2026-10', '1000')
    html = page_text(add_expense(client, amount='1200'))
    assert 'Budget limit reached' in html
    assert card_value(html, 'Remaining Budget') == '₹-200.00'


def test_no_warning_when_budget_not_set(client):
    html = page_text(add_expense(client, amount='500'))
    assert '80% or more' not in html
    assert 'Budget limit reached' not in html
    assert 'No budget is set for this month' in html


def test_decimal_rounding_at_limit(client):
    # 0.1 + 0.2 is 0.30000000000000004 in Python; the app must still see 0.30
    set_budget(client, '2026-10', '0.3')
    add_expense(client, amount='0.1')
    html = page_text(add_expense(client, amount='0.2'))
    assert 'Budget limit reached' in html


def test_delete_expense_updates_totals(client):
    set_budget(client, '2026-10', '1000')
    add_expense(client, title='Keep', amount='100')
    add_expense(client, title='Remove', amount='200')

    conn = get_db_connection()
    row = conn.execute('SELECT id FROM expenses WHERE title = ?', ('Remove',)).fetchone()
    conn.close()

    response = client.post(f'/delete/{row["id"]}', follow_redirects=True)
    html = page_text(response)
    assert 'Expense deleted successfully.' in html
    assert card_value(html, 'Total Spent') == '₹100.00'
    assert card_value(html, 'Remaining Budget') == '₹900.00'
    assert count_expenses() == 1


def test_delete_missing_expense(client):
    html = page_text(client.post('/delete/9999', follow_redirects=True))
    assert 'Expense not found.' in html


def test_delete_needs_post(client):
    assert client.get('/delete/1').status_code == 405



def test_database_error_is_handled(client):
    app.config['DATABASE'] = '/folder_that_does_not_exist/budget.db'
    response = client.get('/')
    assert response.status_code == 200
    assert 'Could not read data from the database.' in page_text(response)
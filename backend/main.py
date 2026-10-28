from contextlib import contextmanager
from datetime import date
from ml_prediction import router as ml_router
from ml_clustering import router as clustering_router
from ml_anomaly import router as anomaly_router
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from reward_engine import router as reward_router

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'credisense.db'
app = FastAPI(title='CrediSense AI')
app.include_router(reward_router)
app.include_router(ml_router)
app.include_router(clustering_router)
app.include_router(anomaly_router)


@contextmanager
def database():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()




def as_dicts(rows):
    return [dict(row) for row in rows]


def require_card(conn, card_id):
    if not conn.execute('SELECT 1 FROM cards WHERE id = ?', (card_id,)).fetchone():
        raise HTTPException(404, 'Credit card not found')


class CreditCard(BaseModel):
    bank_name: str = Field(min_length=1)
    card_name: str = Field(min_length=1)
    credit_limit: float = Field(gt=0)
    outstanding: float = Field(default=0, ge=0)


class Transaction(BaseModel):
    card_id: int = Field(gt=0)
    merchant: str = Field(min_length=1)
    category: str = Field(min_length=1)
    amount: float = Field(gt=0)
    transaction_date: date


class CardReward(BaseModel):
    card_id: int = Field(gt=0)
    category: str = Field(min_length=1)
    reward_percent: float = Field(ge=0, le=100)


class PurchaseRequest(BaseModel):
    category: str = Field(min_length=1)
    amount: float = Field(gt=0)


def validate_card(card):
    if card.outstanding > card.credit_limit:
        raise HTTPException(400, 'Outstanding cannot exceed credit limit')


def insert_card(card):
    validate_card(card)
    with database() as conn:
        result = conn.execute(
            'INSERT INTO cards (bank_name, card_name, credit_limit, outstanding) VALUES (?, ?, ?, ?)',
            (card.bank_name, card.card_name, card.credit_limit, card.outstanding),
        )
        return result.lastrowid


@app.get('/')
def home():
    return {'message': 'Welcome to CrediSense AI'}


@app.get('/health')
def health():
    return {'status': 'healthy'}


@app.post('/cards')
def add_card(card: CreditCard):
    return {'message': 'Credit card added successfully', 'card_id': insert_card(card)}


@app.post('/dashboard/add-card')
def dashboard_add_card(card: CreditCard):
    return {'message': 'Card added successfully', 'card_id': insert_card(card)}


@app.get('/cards')
@app.get('/all-cards')
def get_cards():
    with database() as conn:
        cards = as_dicts(conn.execute('SELECT * FROM cards').fetchall())
    return {'total_cards': len(cards), 'cards': cards}


@app.put('/cards/{card_id}')
def update_card(card_id: int, card: CreditCard):
    validate_card(card)
    with database() as conn:
        result = conn.execute(
            'UPDATE cards SET bank_name=?, card_name=?, credit_limit=?, outstanding=? WHERE id=?',
            (card.bank_name, card.card_name, card.credit_limit, card.outstanding, card_id),
        )
        if not result.rowcount:
            raise HTTPException(404, 'Card not found')
    return {'message': 'Card updated successfully', 'card_id': card_id}


@app.delete('/cards/{card_id}')
def delete_card(card_id: int):
    with database() as conn:
        result = conn.execute('DELETE FROM cards WHERE id=?', (card_id,))
        if not result.rowcount:
            raise HTTPException(404, 'Card not found')
    return {'message': 'Card deleted successfully'}


@app.get('/card-summary')
def card_summary():
    with database() as conn:
        cards = as_dicts(conn.execute(
            'SELECT id, bank_name, card_name, credit_limit, outstanding FROM cards'
        ).fetchall())
    total_limit = sum(c['credit_limit'] for c in cards)
    total_outstanding = sum(c['outstanding'] for c in cards)
    for c in cards:
        c['available_limit'] = round(c['credit_limit'] - c['outstanding'], 2)
        c['utilization_percent'] = round(100 * c['outstanding'] / c['credit_limit'], 2) if c['credit_limit'] else 0
    return {
        'total_cards': len(cards),
        'total_credit_limit': round(total_limit, 2),
        'total_outstanding': round(total_outstanding, 2),
        'total_available_limit': round(total_limit - total_outstanding, 2),
        'overall_utilization_percent': round(100 * total_outstanding / total_limit, 2) if total_limit else 0,
        'cards': cards,
    }


@app.get('/dashboard', include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / 'dashboard.html')


@app.get('/add-card', response_class=HTMLResponse)
def card_form():
    return '''
    <html><body style="font-family:Arial;padding:40px">
      <h2>CrediSense AI - Add Credit Card</h2>
      <form action="/save-card" method="get">
        <p>Bank Name</p><input name="bank_name" required>
        <p>Card Name</p><input name="card_name" required>
        <p>Credit Limit</p><input name="credit_limit" type="number" min="1" required>
        <p>Outstanding Amount</p><input name="outstanding" type="number" min="0" value="0" required>
        <br><br><button type="submit">Add Credit Card</button>
      </form>
    </body></html>'''


@app.get('/save-card')
def save_card(bank_name: str, card_name: str, credit_limit: float, outstanding: float = 0):
    if credit_limit <= 0 or outstanding < 0 or outstanding > credit_limit:
        return {'error': 'Invalid card amounts'}
    insert_card(CreditCard(bank_name=bank_name, card_name=card_name,
                           credit_limit=credit_limit, outstanding=outstanding))
    return {'message': 'Credit Card Added Successfully'}


def transaction_values(t):
    return (t.card_id, t.merchant.strip(), t.category.strip(),
            t.amount, t.transaction_date.isoformat())


def validate_transaction(t):
    if not t.merchant.strip() or not t.category.strip():
        raise HTTPException(400, 'Merchant and category cannot be empty')



@app.post('/transactions')
def add_transaction(transaction: Transaction):
    validate_transaction(transaction)

    with database() as conn:
        require_card(conn, transaction.card_id)

        card = conn.execute(
            'SELECT outstanding, credit_limit FROM cards WHERE id = ?',
            (transaction.card_id,)
        ).fetchone()

        new_outstanding = round(
            card['outstanding'] + transaction.amount, 2
        )

        if new_outstanding > card['credit_limit']:
            raise HTTPException(
                status_code=400,
                detail='Insufficient credit limit'
            )

        result = conn.execute(
            '''
            INSERT INTO transactions
            (card_id, merchant, category, amount,
             transaction_date, balance_applied)
            VALUES (?, ?, ?, ?, ?, 1)
            ''',
            transaction_values(transaction)
        )

        conn.execute(
            'UPDATE cards SET outstanding = ? WHERE id = ?',
            (new_outstanding, transaction.card_id)
        )

        return {
            'message': 'Transaction added successfully',
            'transaction_id': result.lastrowid,
            'updated_outstanding': new_outstanding
        }

      
@app.get('/transactions')
def get_transactions():
    with database() as conn:
        rows = conn.execute('''
            SELECT t.id, t.card_id, c.bank_name, c.card_name,
                   t.merchant, t.category, t.amount, t.transaction_date
            FROM transactions t JOIN cards c ON t.card_id = c.id
            ORDER BY t.transaction_date DESC, t.id DESC
        ''').fetchall()
    return {'total_transactions': len(rows), 'transactions': as_dicts(rows)}


@app.put('/transactions/{transaction_id}')
def update_transaction(transaction_id: int, transaction: Transaction):
    validate_transaction(transaction)

    with database() as conn:
        old = conn.execute(
            '''
            SELECT card_id, amount, balance_applied
            FROM transactions
            WHERE id = ?
            ''',
            (transaction_id,)
        ).fetchone()

        if old is None:
            raise HTTPException(404, 'Transaction not found')

        if old['balance_applied'] != 1:
            raise HTTPException(
                409,
                'Older transaction cannot be edited until balance reconciliation'
            )

        require_card(conn, transaction.card_id)

        old_card_id = old['card_id']
        new_card_id = transaction.card_id

        if old_card_id == new_card_id:
            card = conn.execute(
                'SELECT outstanding, credit_limit FROM cards WHERE id = ?',
                (new_card_id,)
            ).fetchone()

            new_balance = round(
                card['outstanding'] - old['amount'] + transaction.amount, 2
            )

            if new_balance < 0 or new_balance > card['credit_limit']:
                raise HTTPException(400, 'Invalid updated outstanding')

            conn.execute(
                'UPDATE cards SET outstanding = ? WHERE id = ?',
                (new_balance, new_card_id)
            )

        else:
            old_card = conn.execute(
                'SELECT outstanding FROM cards WHERE id = ?',
                (old_card_id,)
            ).fetchone()

            new_card = conn.execute(
                'SELECT outstanding, credit_limit FROM cards WHERE id = ?',
                (new_card_id,)
            ).fetchone()

            if old_card is None:
                raise HTTPException(404, 'Original credit card not found')

            old_balance = round(
                old_card['outstanding'] - old['amount'], 2
            )
            new_balance = round(
                new_card['outstanding'] + transaction.amount, 2
            )

            if old_balance < 0:
                raise HTTPException(409, 'Original card balance mismatch')

            if new_balance > new_card['credit_limit']:
                raise HTTPException(400, 'Insufficient credit limit')

            conn.execute(
                'UPDATE cards SET outstanding = ? WHERE id = ?',
                (old_balance, old_card_id)
            )

            conn.execute(
                'UPDATE cards SET outstanding = ? WHERE id = ?',
                (new_balance, new_card_id)
            )

        conn.execute(
            '''
            UPDATE transactions
            SET card_id = ?, merchant = ?, category = ?,
                amount = ?, transaction_date = ?
            WHERE id = ?
            ''',
            (*transaction_values(transaction), transaction_id)
        )

        return {
            'message': 'Transaction updated successfully',
            'transaction_id': transaction_id
        }


@app.delete('/transactions/{transaction_id}')
def delete_transaction(transaction_id: int):
    with database() as conn:
        old = conn.execute(
            '''
            SELECT card_id, amount, balance_applied
            FROM transactions
            WHERE id = ?
            ''',
            (transaction_id,)
        ).fetchone()

        if old is None:
            raise HTTPException(
                status_code=404,
                detail='Transaction not found'
            )

        updated_outstanding = None

        if old['balance_applied'] == 1:
            card = conn.execute(
                'SELECT outstanding FROM cards WHERE id = ?',
                (old['card_id'],)
            ).fetchone()

            if card is None:
                raise HTTPException(
                    status_code=404,
                    detail='Credit card not found'
                )

            updated_outstanding = round(
                card['outstanding'] - old['amount'], 2
            )

            if updated_outstanding < 0:
                raise HTTPException(
                    status_code=409,
                    detail='Outstanding balance cannot be negative'
                )

            conn.execute(
                'UPDATE cards SET outstanding = ? WHERE id = ?',
                (updated_outstanding, old['card_id'])
            )

        conn.execute(
            'DELETE FROM transactions WHERE id = ?',
            (transaction_id,)
        )

        return {
            'message': 'Transaction deleted successfully',
            'updated_outstanding': updated_outstanding
        }


@app.get('/spending-analytics')
def spending_analytics():
    with database() as conn:
        categories = conn.execute('''
            SELECT category, ROUND(SUM(amount), 2) AS total_amount
            FROM transactions GROUP BY category ORDER BY SUM(amount) DESC
        ''').fetchall()
        totals = conn.execute('''
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS spent FROM transactions
        ''').fetchone()
    return {'total_transactions': totals['count'], 'total_spending': round(totals['spent'], 2),
            'category_wise_spending': as_dicts(categories)}


@app.get('/monthly-spending')
def monthly_spending():
    with database() as conn:
        rows = conn.execute('''
            SELECT substr(transaction_date, 1, 7) AS month,
                   ROUND(SUM(amount), 2) AS total_spending,
                   COUNT(*) AS total_transactions
            FROM transactions GROUP BY substr(transaction_date, 1, 7) ORDER BY month
        ''').fetchall()
    return {'monthly_spending': as_dicts(rows)}


@app.post('/card-rewards')
def add_card_reward(reward: CardReward):
    category = reward.category.strip().title()
    if not category:
        raise HTTPException(400, 'Category cannot be empty')
    with database() as conn:
        require_card(conn, reward.card_id)
        conn.execute('''
            INSERT INTO card_rewards (card_id, category, reward_percent) VALUES (?, ?, ?)
            ON CONFLICT(card_id, category) DO UPDATE SET reward_percent=excluded.reward_percent
        ''', (reward.card_id, category, reward.reward_percent))
    return {'message': 'Card reward saved successfully', 'card_id': reward.card_id,
            'category': category, 'reward_percent': reward.reward_percent}


@app.get('/card-rewards')
def get_card_rewards():
    with database() as conn:
        rewards = as_dicts(conn.execute('''
            SELECT r.id, r.card_id, c.bank_name, c.card_name, r.category, r.reward_percent
            FROM card_rewards r JOIN cards c ON r.card_id=c.id
            ORDER BY c.bank_name, r.category
        ''').fetchall())
    return {'total_rewards': len(rewards), 'rewards': rewards}


@app.get('/reward-catalog')
def get_reward_catalog():
    with database() as conn:
        rewards = as_dicts(conn.execute('''
            SELECT bank_name, card_name, category, reward_percent
            FROM reward_catalog ORDER BY bank_name, card_name, category
        ''').fetchall())
    return {'total_rewards': len(rewards), 'rewards': rewards}


@app.post('/recommend-card')
def recommend_card(purchase: PurchaseRequest):
    category = purchase.category.strip().title()
    if not category:
        raise HTTPException(400, 'Category cannot be empty')
    with database() as conn:
        cards = conn.execute('''
            SELECT c.id, c.bank_name, c.card_name, c.credit_limit, c.outstanding,
                   r.reward_percent
            FROM cards c JOIN reward_catalog r
              ON LOWER(TRIM(c.bank_name))=LOWER(TRIM(r.bank_name))
             AND LOWER(TRIM(c.card_name))=LOWER(TRIM(r.card_name))
            WHERE LOWER(TRIM(r.category))=LOWER(?)
        ''', (category,)).fetchall()
    recommendations = []
    for card in cards:
        available = card['credit_limit'] - card['outstanding']
        if available < purchase.amount:
            continue
        recommendations.append({
            'card_id': card['id'], 'bank_name': card['bank_name'], 'card_name': card['card_name'],
            'reward_percent': card['reward_percent'],
            'estimated_cashback': round(purchase.amount * card['reward_percent'] / 100, 2),
            'available_limit': round(available, 2),
        })
    recommendations.sort(key=lambda r: r['estimated_cashback'], reverse=True)
    return {'category': category, 'purchase_amount': purchase.amount,
            'best_card': recommendations[0] if recommendations else None,
            'recommendations': recommendations
            }

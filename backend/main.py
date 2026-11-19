
"""CrediSense AI 2.0 FastAPI backend, with per-user access controls."""

import math
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import get_current_user, router as auth_router
from bill_management import router as bill_router
from financial_insights import router as insights_router
from ml_anomaly import router as anomaly_router
from ml_clustering import router as clustering_router
from ml_prediction import router as ml_router
from reward_engine import (
    PurchaseRequestV2,
    recommend_card_v2,
    router as reward_router,
)
from config import DB_PATH

BASE_DIR = Path(__file__).resolve().parent
MAX_AMOUNT = 1_000_000_000_000
app = FastAPI(title="CrediSense AI")
app.include_router(auth_router)
app.include_router(reward_router)
app.include_router(bill_router)
app.include_router(ml_router)
app.include_router(clustering_router)
app.include_router(anomaly_router)
app.include_router(insights_router)


@contextmanager
def database(write=False):
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def as_dicts(rows):
    return [dict(row) for row in rows]


def require_card(conn, card_id, user_id):
    row = conn.execute(
        "SELECT id FROM cards WHERE id = ? AND user_id = ?",
        (card_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Credit card not found")


def check_money(value):
    if not math.isfinite(value) or value < 0 or value > MAX_AMOUNT:
        raise HTTPException(422, "Invalid monetary amount")
    if abs(value - round(value, 2)) > 0.000001:
        raise HTTPException(422, "Amounts must have at most two decimal places")
    return round(value, 2)


class CreditCard(BaseModel):
    bank_name: str = Field(min_length=1, max_length=100)
    card_name: str = Field(min_length=1, max_length=100)
    credit_limit: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False)
    outstanding: float = Field(default=0, ge=0, le=MAX_AMOUNT, allow_inf_nan=False)


class Transaction(BaseModel):
    card_id: int = Field(gt=0)
    merchant: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False)
    transaction_date: date


class CardReward(BaseModel):
    card_id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=100)
    reward_percent: float = Field(ge=0, le=100, allow_inf_nan=False)


class PurchaseRequest(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False)


def validate_card(card):
    if not card.bank_name.strip() or not card.card_name.strip():
        raise HTTPException(422, "Bank and card names cannot be empty")
    credit_limit = check_money(card.credit_limit)
    outstanding = check_money(card.outstanding)
    if outstanding > credit_limit:
        raise HTTPException(400, "Outstanding cannot exceed credit limit")
    return credit_limit, outstanding


def insert_card(card, user_id):
    limit, outstanding = validate_card(card)
    with database(write=True) as conn:
        result = conn.execute(
            """INSERT INTO cards
               (bank_name, card_name, credit_limit, outstanding, user_id)
               VALUES (?, ?, ?, ?, ?)""",
            (card.bank_name.strip(), card.card_name.strip(), limit, outstanding, user_id),
        )
        return result.lastrowid


def validate_transaction(t):
    if not t.merchant.strip() or not t.category.strip():
        raise HTTPException(422, "Merchant and category cannot be empty")
    return check_money(t.amount)


def transaction_values(t):
    amount = validate_transaction(t)
    return (t.card_id, t.merchant.strip(), t.category.strip(), amount,
            t.transaction_date.isoformat())


@app.get("/")
def home():
    return {"message": "Welcome to CrediSense AI"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "dashboard.html", headers={"Cache-Control": "no-store"})

@app.get("/manifest.json", include_in_schema=False)
def pwa_manifest():
    return FileResponse(
        BASE_DIR / "manifest.json",
        media_type="application/manifest+json"
    )


@app.get("/icon.svg", include_in_schema=False)
def pwa_icon():
    return FileResponse(
        BASE_DIR / "icon.svg",
        media_type="image/svg+xml"
    )

@app.get("/icon-192.png", include_in_schema=False)
def pwa_icon_192():
    return FileResponse(
        BASE_DIR / "icon-192.png",
        media_type="image/png"
    )


@app.get("/icon-512.png", include_in_schema=False)
def pwa_icon_512():
    return FileResponse(
        BASE_DIR / "icon-512.png",
        media_type="image/png"
    )


@app.get("/add-card", include_in_schema=False)
def old_card_form():
    raise HTTPException(410, "Legacy form is disabled. Use the authenticated dashboard.")


@app.get("/save-card")
def old_save_card():
    raise HTTPException(410, "Legacy route disabled. Use POST /cards.")


@app.post("/cards")
def add_card(card: CreditCard, current_user=Depends(get_current_user)):
    card_id = insert_card(card, current_user["user_id"])
    return {"message": "Credit card added successfully", "card_id": card_id}


@app.post("/dashboard/add-card")
def dashboard_add_card(card: CreditCard, current_user=Depends(get_current_user)):
    card_id = insert_card(card, current_user["user_id"])
    return {"message": "Card added successfully", "card_id": card_id}


@app.get("/cards")
@app.get("/all-cards")
def get_cards(current_user=Depends(get_current_user)):
    with database() as conn:
        cards = as_dicts(conn.execute(
            """SELECT id, bank_name, card_name, credit_limit, outstanding
               FROM cards WHERE user_id = ? ORDER BY id""",
            (current_user["user_id"],),
        ).fetchall())
    return {"total_cards": len(cards), "cards": cards}


@app.put("/cards/{card_id}")
def update_card(card_id: int, card: CreditCard, current_user=Depends(get_current_user)):
    limit, outstanding = validate_card(card)
    with database(write=True) as conn:
        result = conn.execute(
            """UPDATE cards SET bank_name = ?, card_name = ?,
               credit_limit = ?, outstanding = ? WHERE id = ? AND user_id = ?""",
            (card.bank_name.strip(), card.card_name.strip(), limit, outstanding,
             card_id, current_user["user_id"]),
        )
        if not result.rowcount:
            raise HTTPException(404, "Card not found")
    return {"message": "Card updated successfully", "card_id": card_id}


@app.delete("/cards/{card_id}")
def delete_card(card_id: int, current_user=Depends(get_current_user)):
    with database(write=True) as conn:
        result = conn.execute(
            "DELETE FROM cards WHERE id = ? AND user_id = ?",
            (card_id, current_user["user_id"]),
        )
        if not result.rowcount:
            raise HTTPException(404, "Card not found")
    return {"message": "Card deleted successfully"}


@app.get("/card-summary")
def card_summary(current_user=Depends(get_current_user)):
    with database() as conn:
        cards = as_dicts(conn.execute(
            """SELECT id, bank_name, card_name, credit_limit, outstanding
               FROM cards WHERE user_id = ? ORDER BY id""",
            (current_user["user_id"],),
        ).fetchall())
    total_limit = round(sum(c["credit_limit"] for c in cards), 2)
    total_outstanding = round(sum(c["outstanding"] for c in cards), 2)
    for card in cards:
        card["available_limit"] = round(card["credit_limit"] - card["outstanding"], 2)
        card["utilization_percent"] = (
            round(100 * card["outstanding"] / card["credit_limit"], 2)
            if card["credit_limit"] else 0
        )
    return {
        "total_cards": len(cards),
        "total_credit_limit": total_limit,
        "total_outstanding": total_outstanding,
        "total_available_limit": round(total_limit - total_outstanding, 2),
        "overall_utilization_percent": (
            round(100 * total_outstanding / total_limit, 2) if total_limit else 0
        ),
        "cards": cards,
    }


@app.post("/transactions")
def add_transaction(transaction: Transaction, current_user=Depends(get_current_user)):
    amount = validate_transaction(transaction)
    user_id = current_user["user_id"]
    with database(write=True) as conn:
        card = conn.execute(
            "SELECT outstanding, credit_limit FROM cards WHERE id = ? AND user_id = ?",
            (transaction.card_id, user_id),
        ).fetchone()
        if card is None:
            raise HTTPException(404, "Card not found")
        new_outstanding = round(card["outstanding"] + amount, 2)
        if new_outstanding > card["credit_limit"]:
            raise HTTPException(400, "Insufficient credit limit")
        result = conn.execute(
            """INSERT INTO transactions
               (card_id, merchant, category, amount, transaction_date, balance_applied)
               VALUES (?, ?, ?, ?, ?, 1)""",
            transaction_values(transaction),
        )
        conn.execute(
            "UPDATE cards SET outstanding = ? WHERE id = ? AND user_id = ?",
            (new_outstanding, transaction.card_id, user_id),
        )
    return {
        "message": "Transaction added successfully",
        "transaction_id": result.lastrowid,
        "updated_outstanding": new_outstanding,
    }


@app.get("/transactions")
def get_transactions(current_user=Depends(get_current_user)):
    with database() as conn:
        rows = conn.execute(
            """SELECT t.id, t.card_id, c.bank_name, c.card_name, t.merchant,
                      t.category, t.amount, t.transaction_date
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE c.user_id = ?
               ORDER BY t.transaction_date DESC, t.id DESC""",
            (current_user["user_id"],),
        ).fetchall()
    return {"total_transactions": len(rows), "transactions": as_dicts(rows)}


@app.put("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: int,
    transaction: Transaction,
    current_user=Depends(get_current_user),
):
    amount = validate_transaction(transaction)
    user_id = current_user["user_id"]
    with database(write=True) as conn:
        old = conn.execute(
            """SELECT t.card_id, t.amount, t.balance_applied
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE t.id = ? AND c.user_id = ?""",
            (transaction_id, user_id),
        ).fetchone()
        if old is None:
            raise HTTPException(404, "Transaction not found")
        if old["balance_applied"] != 1:
            raise HTTPException(409, "Older transaction requires balance reconciliation")
        require_card(conn, transaction.card_id, user_id)
        old_card_id = old["card_id"]
        new_card_id = transaction.card_id
        if old_card_id == new_card_id:
            card = conn.execute(
                "SELECT outstanding, credit_limit FROM cards WHERE id = ? AND user_id = ?",
                (new_card_id, user_id),
            ).fetchone()
            new_balance = round(card["outstanding"] - old["amount"] + amount, 2)
            if new_balance < 0 or new_balance > card["credit_limit"]:
                raise HTTPException(400, "Invalid updated outstanding")
            conn.execute(
                "UPDATE cards SET outstanding = ? WHERE id = ? AND user_id = ?",
                (new_balance, new_card_id, user_id),
            )
        else:
            old_card = conn.execute(
                "SELECT outstanding FROM cards WHERE id = ? AND user_id = ?",
                (old_card_id, user_id),
            ).fetchone()
            new_card = conn.execute(
                "SELECT outstanding, credit_limit FROM cards WHERE id = ? AND user_id = ?",
                (new_card_id, user_id),
            ).fetchone()
            if old_card is None or new_card is None:
                raise HTTPException(404, "Card not found")
            old_balance = round(old_card["outstanding"] - old["amount"], 2)
            new_balance = round(new_card["outstanding"] + amount, 2)
            if old_balance < 0:
                raise HTTPException(409, "Original card balance mismatch")
            if new_balance > new_card["credit_limit"]:
                raise HTTPException(400, "Insufficient credit limit")
            conn.execute(
                "UPDATE cards SET outstanding = ? WHERE id = ? AND user_id = ?",
                (old_balance, old_card_id, user_id),
            )
            conn.execute(
                "UPDATE cards SET outstanding = ? WHERE id = ? AND user_id = ?",
                (new_balance, new_card_id, user_id),
            )
        result = conn.execute(
            """UPDATE transactions SET card_id = ?, merchant = ?, category = ?,
                      amount = ?, transaction_date = ?
               WHERE id = ? AND card_id IN
                     (SELECT id FROM cards WHERE user_id = ?)""",
            (*transaction_values(transaction), transaction_id, user_id),
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Transaction changed during update")
    return {"message": "Transaction updated successfully", "transaction_id": transaction_id}


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    updated_outstanding = None
    with database(write=True) as conn:
        old = conn.execute(
            """SELECT t.card_id, t.amount, t.balance_applied
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE t.id = ? AND c.user_id = ?""",
            (transaction_id, user_id),
        ).fetchone()
        if old is None:
            raise HTTPException(404, "Transaction not found")
        if old["balance_applied"] == 1:
            card = conn.execute(
                "SELECT outstanding FROM cards WHERE id = ? AND user_id = ?",
                (old["card_id"], user_id),
            ).fetchone()
            if card is None:
                raise HTTPException(404, "Card not found")
            updated_outstanding = round(card["outstanding"] - old["amount"], 2)
            if updated_outstanding < 0:
                raise HTTPException(409, "Outstanding balance cannot be negative")
            conn.execute(
                "UPDATE cards SET outstanding = ? WHERE id = ? AND user_id = ?",
                (updated_outstanding, old["card_id"], user_id),
            )
        result = conn.execute(
            """DELETE FROM transactions WHERE id = ?
               AND card_id IN (SELECT id FROM cards WHERE user_id = ?)""",
            (transaction_id, user_id),
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Transaction changed during deletion")
    return {"message": "Transaction deleted successfully",
            "updated_outstanding": updated_outstanding}


@app.get("/spending-analytics")
def spending_analytics(current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    with database() as conn:
        categories = conn.execute(
            """SELECT t.category, ROUND(SUM(t.amount), 2) AS total_amount
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE c.user_id = ? GROUP BY t.category
               ORDER BY SUM(t.amount) DESC""",
            (user_id,),
        ).fetchall()
        totals = conn.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(t.amount), 0) AS spent
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE c.user_id = ?""",
            (user_id,),
        ).fetchone()
    return {"total_transactions": totals["count"],
            "total_spending": round(totals["spent"], 2),
            "category_wise_spending": as_dicts(categories)}


@app.get("/monthly-spending")
def monthly_spending(current_user=Depends(get_current_user)):
    with database() as conn:
        rows = conn.execute(
            """SELECT substr(t.transaction_date, 1, 7) AS month,
                      ROUND(SUM(t.amount), 2) AS total_spending,
                      COUNT(*) AS total_transactions
               FROM transactions t JOIN cards c ON c.id = t.card_id
               WHERE c.user_id = ?
               GROUP BY substr(t.transaction_date, 1, 7)
               ORDER BY month""",
            (current_user["user_id"],),
        ).fetchall()
    return {"monthly_spending": as_dicts(rows)}


@app.post("/card-rewards")
def add_card_reward(reward: CardReward, current_user=Depends(get_current_user)):
    category = reward.category.strip().title()
    if not category:
        raise HTTPException(422, "Category cannot be empty")
    with database(write=True) as conn:
        require_card(conn, reward.card_id, current_user["user_id"])
        conn.execute(
            """INSERT INTO card_rewards (card_id, category, reward_percent)
               VALUES (?, ?, ?)
               ON CONFLICT(card_id, category)
               DO UPDATE SET reward_percent = excluded.reward_percent""",
            (reward.card_id, category, reward.reward_percent),
        )
    return {"message": "Card reward saved successfully",
            "card_id": reward.card_id, "category": category,
            "reward_percent": reward.reward_percent}


@app.get("/card-rewards")
def get_card_rewards(current_user=Depends(get_current_user)):
    with database() as conn:
        rewards = as_dicts(conn.execute(
            """SELECT r.id, r.card_id, c.bank_name, c.card_name,
                      r.category, r.reward_percent
               FROM card_rewards r JOIN cards c ON c.id = r.card_id
               WHERE c.user_id = ? ORDER BY c.bank_name, r.category""",
            (current_user["user_id"],),
        ).fetchall())
    return {"total_rewards": len(rewards), "rewards": rewards}


@app.get("/reward-catalog")
def get_reward_catalog():
    # Public, demo-only catalog. Contains no account-specific data.
    with database() as conn:
        rewards = as_dicts(conn.execute(
            """SELECT bank_name, card_name, category, reward_percent
               FROM reward_catalog ORDER BY bank_name, card_name, category"""
        ).fetchall())
    return {"total_rewards": len(rewards), "rewards": rewards}


@app.post("/recommend-card")
def recommend_card(purchase: PurchaseRequest, current_user=Depends(get_current_user)):
    # Legacy endpoint uses the v2 engine so merchants, minimums and caps apply.
    category = purchase.category.strip()
    if not category:
        raise HTTPException(422, "Category cannot be empty")
    check_money(purchase.amount)
    return recommend_card_v2(
        PurchaseRequestV2(category=category, amount=purchase.amount, merchant=None),
        current_user=current_user,
    )

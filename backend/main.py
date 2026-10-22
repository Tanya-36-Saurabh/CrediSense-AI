
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sqlite3

app = FastAPI(title="CrediSense AI")


class CreditCard(BaseModel):
    bank_name: str
    card_name: str
    credit_limit: float = Field(gt=0)
    outstanding: float = Field(default=0, ge=0)


@app.get("/")
def home():
    return {"message": "Welcome to CrediSense AI"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/cards")
def add_card(card: CreditCard):
    if card.outstanding > card.credit_limit:
        raise HTTPException(
            status_code=400,
            detail="Outstanding cannot exceed credit limit"
        )

    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO cards
        (bank_name, card_name, credit_limit, outstanding)
        VALUES (?, ?, ?, ?)
        """,
        (
            card.bank_name,
            card.card_name,
            card.credit_limit,
            card.outstanding
        )
    )

    conn.commit()
    card_id = cursor.lastrowid
    conn.close()

    return {
        "message": "Credit card added successfully",
        "card_id": card_id
    }


@app.get("/cards")
def get_cards():
    conn = sqlite3.connect("credisense.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards")

    cards = cursor.fetchall()
    conn.close()

    return {
        "total_cards": len(cards),
        "cards": [dict(card) for card in cards]
    }


@app.get("/all-cards")
def show_all_cards():
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cards")
    cards = cursor.fetchall()

    conn.close()

    result = []

    for card in cards:
        result.append({
            "id": card[0],
            "bank_name": card[1],
            "card_name": card[2],
            "credit_limit": card[3],
            "outstanding": card[4]
        })

    return {
        "total_cards": len(result),
        "cards": result
    }



from fastapi.responses import HTMLResponse

@app.get("/add-card", response_class=HTMLResponse)
def card_form():
    return """
    <html>
    <body style="font-family:Arial; padding:40px;">
        <h2>CrediSense AI - Add Credit Card</h2>

        <form action="/save-card" method="get">
            <p>Bank Name</p>
            <input name="bank_name" required>

            <p>Card Name</p>
            <input name="card_name" required>

            <p>Credit Limit</p>
            <input name="credit_limit" type="number" min="1" required>

            <p>Outstanding Amount</p>
            <input name="outstanding" type="number" min="0" value="0" required>

            <br><br>
            <button type="submit">Add Credit Card</button>
        </form>
    </body>
    </html>
    """


@app.get("/save-card")
def save_card(bank_name: str, card_name: str,
              credit_limit: float, outstanding: float = 0):

    if credit_limit <= 0 or outstanding < 0 or outstanding > credit_limit:
        return {"error": "Invalid card amounts"}

    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO cards
        (bank_name, card_name, credit_limit, outstanding)
        VALUES (?, ?, ?, ?)""",
        (bank_name, card_name, credit_limit, outstanding)
    )

    conn.commit()
    conn.close()

    return {"message": "Credit Card Added Successfully"}




@app.get("/card-summary")
def card_summary():
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, bank_name, card_name, credit_limit, outstanding FROM cards"
    )

    cards = cursor.fetchall()
    conn.close()

    result = []
    total_limit = 0
    total_outstanding = 0

    for card in cards:
        card_id, bank, name, limit, outstanding = card

        available = limit - outstanding
        utilization = (outstanding / limit) * 100 if limit > 0 else 0

        total_limit += limit
        total_outstanding += outstanding

        result.append({
            "id": card_id,
            "bank_name": bank,
            "card_name": name,
            "credit_limit": limit,
            "outstanding": outstanding,
            "available_limit": round(available, 2),
            "utilization_percent": round(utilization, 2)
        })

    total_available = total_limit - total_outstanding
    overall_utilization = (
        (total_outstanding / total_limit) * 100
        if total_limit > 0 else 0
    )

    return {
        "total_cards": len(result),
        "total_credit_limit": round(total_limit, 2),
        "total_outstanding": round(total_outstanding, 2),
        "total_available_limit": round(total_available, 2),
        "overall_utilization_percent": round(overall_utilization, 2),
        "cards": result
    }




@app.get("/card-summary")
def card_summary():
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT bank_name, card_name, credit_limit, outstanding FROM cards"
    )

    cards = cursor.fetchall()
    conn.close()

    result = []

    for bank, name, limit, outstanding in cards:
        available = limit - outstanding
        utilization = (outstanding / limit) * 100 if limit > 0 else 0

        result.append({
            "bank_name": bank,
            "card_name": name,
            "credit_limit": limit,
            "outstanding": outstanding,
            "available_limit": round(available, 2),
            "utilization_percent": round(utilization, 2)
        })

    return {"cards": result}






@app.delete("/cards/{card_id}")
def delete_card(card_id: int):
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM cards WHERE id = ?",
        (card_id,)
    )

    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    return {"message": "Card deleted successfully"}






from fastapi.responses import FileResponse
from pathlib import Path

@app.get("/dashboard", include_in_schema=False)
def dashboard():
    file_path = Path(__file__).parent / "dashboard.html"
    return FileResponse(file_path)






@app.post("/dashboard/add-card")
def dashboard_add_card(card: CreditCard):
    if card.outstanding > card.credit_limit:
        raise HTTPException(
            status_code=400,
            detail="Outstanding cannot exceed credit limit"
        )

    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO cards
        (bank_name, card_name, credit_limit, outstanding)
        VALUES (?, ?, ?, ?)
        """,
        (
            card.bank_name,
            card.card_name,
            card.credit_limit,
            card.outstanding
        )
    )

    conn.commit()
    card_id = cursor.lastrowid
    conn.close()

    return {
        "message": "Card added successfully",
        "card_id": card_id
    }





@app.put("/cards/{card_id}")
def update_card(card_id: int, card: CreditCard):
    if card.outstanding > card.credit_limit:
        raise HTTPException(
            status_code=400,
            detail="Outstanding cannot exceed credit limit"
        )

    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE cards
        SET bank_name = ?,
            card_name = ?,
            credit_limit = ?,
            outstanding = ?
        WHERE id = ?
        """,
        (
            card.bank_name,
            card.card_name,
            card.credit_limit,
            card.outstanding,
            card_id
        )
    )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        raise HTTPException(
            status_code=404,
            detail="Card not found"
        )

    return {
        "message": "Card updated successfully",
        "card_id": card_id
    }



from datetime import date

class Transaction(BaseModel):
    card_id: int = Field(gt=0)
    merchant: str = Field(min_length=1)
    category: str = Field(min_length=1)
    amount: float = Field(gt=0)
    transaction_date: date


@app.post("/transactions")
def add_transaction(transaction: Transaction):
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM cards WHERE id = ?",
        (transaction.card_id,)
    )

    card = cursor.fetchone()

    if card is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Credit card not found"
        )

    cursor.execute(
        """
        INSERT INTO transactions
        (card_id, merchant, category, amount, transaction_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            transaction.card_id,
            transaction.merchant.strip(),
            transaction.category.strip(),
            transaction.amount,
            transaction.transaction_date.isoformat()
        )
    )

    conn.commit()
    transaction_id = cursor.lastrowid
    conn.close()

    return {
        "message": "Transaction added successfully",
        "transaction_id": transaction_id
    }




@app.get("/transactions")
def get_transactions():
    conn = sqlite3.connect("credisense.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            transactions.id,
            transactions.card_id,
            cards.bank_name,
            cards.card_name,
            transactions.merchant,
            transactions.category,
            transactions.amount,
            transactions.transaction_date
        FROM transactions
        JOIN cards
        ON transactions.card_id = cards.id
        ORDER BY transactions.transaction_date DESC,
                 transactions.id DESC
    """)

    transactions = cursor.fetchall()
    conn.close()

    return {
        "total_transactions": len(transactions),
        "transactions": [
            dict(transaction) for transaction in transactions
        ]
    }



@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int):
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM transactions WHERE id = ?",
        (transaction_id,)
    )

    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return {
        "message": "Transaction deleted successfully"
    }



@app.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: int, transaction: Transaction):
    conn = sqlite3.connect("credisense.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM cards WHERE id = ?",
        (transaction.card_id,)
    )

    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Credit card not found"
        )

    cursor.execute(
        """
        UPDATE transactions
        SET card_id = ?,
            merchant = ?,
            category = ?,
            amount = ?,
            transaction_date = ?
        WHERE id = ?
        """,
        (
            transaction.card_id,
            transaction.merchant.strip(),
            transaction.category.strip(),
            transaction.amount,
            transaction.transaction_date.isoformat(),
            transaction_id
        )
    )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    return {
        "message": "Transaction updated successfully",
        "transaction_id": transaction_id
    }



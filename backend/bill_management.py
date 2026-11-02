
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/bills", tags=["Bill Management"])

DB_PATH = Path(__file__).resolve().parent / "credisense.db"


class BillInput(BaseModel):
    card_id: int = Field(gt=0)
    bill_amount: float = Field(gt=0)
    due_date: str


@router.post("")
def create_bill(bill: BillInput):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")

            card = conn.execute(
                "SELECT id FROM cards WHERE id = ?",
                (bill.card_id,)
            ).fetchone()

            if card is None:
                raise HTTPException(
                    status_code=404,
                    detail="Card not found"
                )

            cursor = conn.execute("""
                INSERT INTO bills (card_id, bill_amount, due_date)
                VALUES (?, ?, ?)
            """, (bill.card_id, bill.bill_amount, bill.due_date))

            return {
                "message": "Bill created successfully",
                "bill_id": cursor.lastrowid,
                "card_id": bill.card_id,
                "bill_amount": bill.bill_amount,
                "due_date": bill.due_date,
                "status": "Unpaid"
            }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to create bill"
        ) from exc


@router.get("")
def get_bills():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT
                    b.id,
                    b.card_id,
                    c.bank_name,
                    c.card_name,
                    b.bill_amount,
                    b.due_date,
                    b.status
                FROM bills AS b
                JOIN cards AS c ON b.card_id = c.id
                ORDER BY b.due_date
            """).fetchall()

            return {
                "total_bills": len(rows),
                "bills": [dict(row) for row in rows]
            }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch bills"
        ) from exc



from datetime import date


class PaymentInput(BaseModel):
    bill_id: int = Field(gt=0)
    amount: float = Field(gt=0, allow_inf_nan=False)
    payment_date: date


@router.post("/payments")
def add_bill_payment(payment: PaymentInput):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")

            bill = conn.execute("""
                SELECT id, bill_amount, status
                FROM bills
                WHERE id = ?
            """, (payment.bill_id,)).fetchone()

            if bill is None:
                raise HTTPException(
                    status_code=404,
                    detail="Bill not found"
                )

            paid_row = conn.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM bill_payments
                WHERE bill_id = ?
            """, (payment.bill_id,)).fetchone()

            already_paid = round(float(paid_row[0]), 2)
            bill_amount = round(float(bill[1]), 2)
            remaining = round(bill_amount - already_paid, 2)

            if payment.amount > remaining + 0.000001:
                raise HTTPException(
                    status_code=400,
                    detail="Payment exceeds remaining bill amount"
                )

            if remaining <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Bill is already fully paid"
                )

            cursor = conn.execute("""
                INSERT INTO bill_payments (
                    bill_id, amount, payment_date
                )
                VALUES (?, ?, ?)
            """, (
                payment.bill_id,
                payment.amount,
                payment.payment_date.isoformat()
            ))

            total_paid = round(
                already_paid + payment.amount, 2
            )

            status = (
                "Paid" if total_paid >= bill_amount
                else "Partial"
            )

            conn.execute("""
                UPDATE bills
                SET status = ?
                WHERE id = ?
            """, (status, payment.bill_id))

            return {
                "message": "Payment recorded successfully",
                "payment_id": cursor.lastrowid,
                "bill_id": payment.bill_id,
                "amount_paid": payment.amount,
                "total_paid": total_paid,
                "remaining_amount": round(
                    max(0, bill_amount - total_paid), 2
                ),
                "status": status
            }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to record payment"
        ) from exc



@router.get("/{bill_id}/payments")
def get_payment_history(bill_id: int):
    if bill_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Invalid bill ID"
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            bill = conn.execute(
                "SELECT id, bill_amount, status FROM bills WHERE id = ?",
                (bill_id,)
            ).fetchone()

            if bill is None:
                raise HTTPException(
                    status_code=404,
                    detail="Bill not found"
                )

            payments = conn.execute("""
                SELECT id, bill_id, amount, payment_date, created_at
                FROM bill_payments
                WHERE bill_id = ?
                ORDER BY payment_date, id
            """, (bill_id,)).fetchall()

            total_paid = round(
                sum(float(row["amount"]) for row in payments), 2
            )

            return {
                "bill_id": bill_id,
                "bill_amount": bill["bill_amount"],
                "total_paid": total_paid,
                "remaining_amount": round(
                    max(0, bill["bill_amount"] - total_paid), 2
                ),
                "status": bill["status"],
                "payments": [dict(row) for row in payments]
            }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch payment history"
        ) from exc

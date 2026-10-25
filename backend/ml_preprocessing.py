import sqlite3
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "credisense.db"
OUTPUT_PATH = BASE_DIR / "monthly_spending.csv"


def parse_date(value):
    if not value:
        return None

    text = str(value).strip()

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m/%d/%Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def load_transactions():
    if not DB_PATH.exists():
        print("Database not found!")
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]

        if "transactions" not in tables:
            print("Transactions table not found!")
            return []

        rows = conn.execute(
            "SELECT * FROM transactions"
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def prepare_monthly_data(transactions):
    monthly = defaultdict(float)
    skipped = 0

    for transaction in transactions:

        amount = transaction.get("amount")

        date_value = (
            transaction.get("transaction_date")
            or transaction.get("date")
            or transaction.get("created_at")
        )

        date = parse_date(date_value)

        try:
            amount = float(amount)
        except (ValueError, TypeError):
            skipped += 1
            continue

        if date is None or amount <= 0:
            skipped += 1
            continue

        transaction_type = str(
            transaction.get("transaction_type")
            or transaction.get("type")
            or ""
        ).strip().lower()

        if transaction_type in [
            "income", "credit", "refund", "payment"
        ]:
            skipped += 1
            continue

        month = date.strftime("%Y-%m")

        monthly[month] += amount

    result = []

    for month in sorted(monthly):
        result.append({
            "month": month,
            "total_spending": round(monthly[month], 2)
        })

    print("Skipped transactions:", skipped)

    return result


def save_monthly_data(data):

    if not data:
        print("No valid spending data available.")
        return

    with open(
        OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=["month", "total_spending"]
        )

        writer.writeheader()
        writer.writerows(data)

    print("Monthly spending data saved successfully!")
    print("File:", OUTPUT_PATH)


def main():

    transactions = load_transactions()

    print("Total transactions:", len(transactions))

    monthly_data = prepare_monthly_data(transactions)

    print("Total months:", len(monthly_data))

    save_monthly_data(monthly_data)


if __name__ == "__main__":
    main()
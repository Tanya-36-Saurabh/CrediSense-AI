
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "demo_anomaly_transactions.csv"

categories = ["Shopping", "Food", "Travel", "Groceries", "Bills"]

start_date = datetime(2026, 1, 1)

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow(["date", "category", "amount", "is_demo_anomaly"])

    for i in range(500):
        date = start_date + timedelta(days=random.randint(0, 270))
        category = random.choice(categories)

        is_anomaly = 1 if i < 20 else 0

        if is_anomaly:
            amount = round(random.uniform(25000, 80000), 2)
        else:
            amount = round(random.uniform(100, 5000), 2)

        writer.writerow([
            date.strftime("%Y-%m-%d"),
            category,
            amount,
            is_anomaly
        ])

print("Synthetic anomaly dataset generated successfully!")
print("Total transactions: 500")
print("Injected demo anomalies: 20")
print("Saved to:", OUTPUT_FILE)

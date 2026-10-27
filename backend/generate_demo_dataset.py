import csv
import random
import math
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "demo_monthly_spending.csv"

random.seed(42)

data = []

for i in range(24):
    year = 2024 + (9 + i) // 12
    month = (9 + i) % 12 + 1

    trend = i * 180
    seasonal = 2200 * math.sin(2 * math.pi * i / 12)
    noise = random.gauss(0, 900)

    spending = max(
        1000,
        18000 + trend + seasonal + noise
    )

    data.append({
        "month": f"{year}-{month:02d}",
        "total_spending": round(spending, 2)
    })

with open(
    OUTPUT_FILE,
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

print("Synthetic dataset created successfully!")
print("Total months:", len(data))
print("File:", OUTPUT_FILE)
import csv
import math
from pathlib import Path

import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "monthly_spending.csv"
MODEL_PATH = BASE_DIR / "random_forest_model.pkl"


def load_data():

    if not DATA_PATH.exists():
        print("monthly_spending.csv not found!")
        return None

    data = []

    with open(DATA_PATH, "r", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:
            try:
                month = row["month"]
                spending = float(row["total_spending"])

                if not math.isfinite(spending) or spending < 0:
                    continue

                data.append((month, spending))

            except (ValueError, KeyError, TypeError):
                continue

    data.sort(key=lambda x: x[0])

    months = [row[0] for row in data]
    spending = [row[1] for row in data]

    if len(months) != len(set(months)):
        print("Duplicate months found. Check the CSV.")
        return None

    month_numbers = []

    for month in months:
        try:
            year, month_value = map(int, month.split("-"))

            if not 1 <= month_value <= 12:
                raise ValueError

            month_numbers.append(year * 12 + month_value)

        except ValueError:
            print("Invalid month:", month)
            return None

    for i in range(1, len(month_numbers)):
        if month_numbers[i] - month_numbers[i - 1] != 1:
            print("Missing months detected in spending data.")
            print("Please complete monthly data before training.")
            return None

    print("Total months available:", len(data))

    return np.array(spending, dtype=float)


def prepare_features(spending):

    X = []
    y = []

    for i in range(3, len(spending)):

        features = [
            spending[i - 1],
            spending[i - 2],
            spending[i - 3]
        ]

        X.append(features)
        y.append(spending[i])

    return np.array(X), np.array(y)


def train_model():

    spending = load_data()

    if spending is None:
        return

    if len(spending) < 12:
        print("Not enough historical data for meaningful training.")
        print("At least 12 consecutive months are required.")
        print("No model was trained.")
        return

    X, y = prepare_features(spending)

    split = int(len(X) * 0.8)

    X_train = X[:split]
    X_test = X[split:]

    y_train = y[:split]
    y_test = y[split:]

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)

    rmse = math.sqrt(
        mean_squared_error(y_test, predictions)
    )

    print("\nModel Evaluation")
    print("---------------------")
    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))

    print("\nTest Predictions")

    for actual, predicted in zip(y_test, predictions):
        print(
            "Actual:", round(actual, 2),
            "| Predicted:", round(predicted, 2)
        )

    # Retrain on all available months after evaluation

    final_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42
    )

    final_model.fit(X, y)

    joblib.dump(final_model, MODEL_PATH)

    print("\nModel saved successfully!")

    last_three = [
        spending[-1],
        spending[-2],
        spending[-3]
    ]

    next_month_prediction = final_model.predict(
        [last_three]
    )[0]

    print(
        "Next Month Predicted Spending: Rs.",
        round(max(0, next_month_prediction), 2)
    )


if __name__ == "__main__":
    train_model()
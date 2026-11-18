
import csv
import math
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)


BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "demo_monthly_spending.csv"
MODEL_PATH = BASE_DIR / "random_forest_model.pkl"

MIN_MONTHS = 12


def load_data():
    if not DATA_PATH.is_file():
        print("Error: demo_monthly_spending.csv not found!")
        return None

    data = []

    try:
        with DATA_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            if not reader.fieldnames:
                print("Error: CSV file is empty.")
                return None

            required_columns = {"month", "total_spending"}

            if not required_columns.issubset(reader.fieldnames):
                print("Error: Required CSV columns are missing.")
                return None

            for line_number, row in enumerate(reader, start=2):
                try:
                    month = row["month"].strip()
                    spending = float(row["total_spending"])

                    if not math.isfinite(spending) or spending < 0:
                        raise ValueError("Invalid spending amount")

                    year_text, month_text = month.split("-")

                    if (
                        len(year_text) != 4
                        or len(month_text) != 2
                        or not year_text.isdigit()
                        or not month_text.isdigit()
                    ):
                        raise ValueError("Invalid month format")

                    year = int(year_text)
                    month_value = int(month_text)

                    if year < 1 or not 1 <= month_value <= 12:
                        raise ValueError("Invalid calendar month")

                    month_number = year * 12 + month_value

                    data.append(
                        (month, month_number, spending)
                    )

                except (ValueError, TypeError, AttributeError):
                    print(
                        f"Error: Invalid data at CSV line {line_number}."
                    )
                    return None

    except (OSError, csv.Error) as exc:
        print("Error: Unable to read dataset:", exc)
        return None

    if len(data) < MIN_MONTHS:
        print(
            f"Error: At least {MIN_MONTHS} months "
            "of data are required."
        )
        return None

    months = [row[0] for row in data]

    if len(months) != len(set(months)):
        print("Error: Duplicate months found.")
        return None

    sorted_data = sorted(
        data,
        key=lambda row: row[1]
    )

    if data != sorted_data:
        print(
            "Error: CSV months are not in chronological order."
        )
        return None

    for index in range(1, len(data)):
        previous_month = data[index - 1][1]
        current_month = data[index][1]

        if current_month - previous_month != 1:
            print(
                "Error: Missing or non-consecutive months "
                "detected."
            )
            return None

    spending = np.array(
        [row[2] for row in data],
        dtype=float
    )

    print("Total months available:", len(spending))
    print("Dataset validation: PASS")

    return spending


def prepare_features(spending):
    X = []
    y = []

    for index in range(3, len(spending)):
        X.append([
            spending[index - 1],
            spending[index - 2],
            spending[index - 3]
        ])

        y.append(spending[index])

    return (
        np.array(X, dtype=float),
        np.array(y, dtype=float)
    )


def save_model_safely(model):
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".pkl",
            prefix="random_forest_",
            dir=BASE_DIR,
            delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        joblib.dump(model, temporary_path)

        # Replace the existing model only after saving succeeds.
        os.replace(temporary_path, MODEL_PATH)

        print("\nModel saved successfully!")
        return True

    except (OSError, ValueError, TypeError) as exc:
        print("Error: Unable to save model:", exc)
        return False

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def train_model():
    spending = load_data()

    if spending is None:
        print("Training cancelled. Existing model unchanged.")
        return

    X, y = prepare_features(spending)

    if len(X) < 2:
        print("Error: Not enough samples for evaluation.")
        return

    split = int(len(X) * 0.8)

    if split <= 0 or split >= len(X):
        print("Error: Invalid training/test split.")
        return

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

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    rmse = math.sqrt(
        mean_squared_error(
            y_test,
            predictions
        )
    )

    print("\nModel Evaluation")
    print("---------------------")
    print("Training samples:", len(X_train))
    print("Testing samples:", len(X_test))
    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))

    print("\nTest Predictions")

    for actual, predicted in zip(y_test, predictions):
        print(
            "Actual:", round(float(actual), 2),
            "| Predicted:", round(float(predicted), 2)
        )

    # Train the final model on all validated demo data.
    final_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42
    )

    final_model.fit(X, y)

    last_three = np.array(
        [[
            spending[-1],
            spending[-2],
            spending[-3]
        ]],
        dtype=float
    )

    next_month_prediction = float(
        final_model.predict(last_three)[0]
    )

    if not math.isfinite(next_month_prediction):
        print("Error: Model produced an invalid prediction.")
        print("Existing model unchanged.")
        return

    if not save_model_safely(final_model):
        print("Existing model was not intentionally replaced.")
        return

    print(
        "Next Month Predicted Spending: Rs.",
        round(max(0, next_month_prediction), 2)
    )

    print("Data Source: Synthetic Demo")
    print("Training Complete!")


if __name__ == "__main__":
    train_model()

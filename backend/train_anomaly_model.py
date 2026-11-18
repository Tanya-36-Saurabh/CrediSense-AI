
import math
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score
)


BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "demo_anomaly_transactions.csv"
MODEL_PATH = BASE_DIR / "anomaly_model.pkl"

MIN_SAMPLES = 10


def load_data():
    if not DATA_PATH.is_file():
        print("Error: demo_anomaly_transactions.csv not found!")
        return None

    try:
        df = pd.read_csv(DATA_PATH)

    except (OSError, ValueError, pd.errors.ParserError) as exc:
        print("Error: Unable to read dataset:", exc)
        return None

    required_columns = {
        "amount",
        "is_demo_anomaly"
    }

    if not required_columns.issubset(df.columns):
        print("Error: Required CSV columns are missing.")
        return None

    if len(df) < MIN_SAMPLES:
        print(
            f"Error: At least {MIN_SAMPLES} transactions "
            "are required."
        )
        return None

    try:
        amounts = pd.to_numeric(
            df["amount"],
            errors="raise"
        ).to_numpy(dtype=float)

        labels = pd.to_numeric(
            df["is_demo_anomaly"],
            errors="raise"
        ).to_numpy(dtype=float)

    except (ValueError, TypeError) as exc:
        print("Error: Invalid dataset values:", exc)
        return None

    if not np.all(np.isfinite(amounts)):
        print("Error: Amounts contain NaN or infinity.")
        return None

    if np.any(amounts <= 0):
        print("Error: Transaction amounts must be positive.")
        return None

    if not np.all(np.isfinite(labels)):
        print("Error: Anomaly labels contain invalid values.")
        return None

    if not np.all(np.isin(labels, [0, 1])):
        print("Error: Anomaly labels must be 0 or 1.")
        return None

    if len(np.unique(amounts)) < 2:
        print("Error: Dataset needs different transaction amounts.")
        return None

    X = amounts.reshape(-1, 1)
    y_true = labels.astype(int)

    print("Total transactions:", len(df))
    print("Dataset validation: PASS")

    return X, y_true


def save_model_safely(model):
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="anomaly_",
            suffix=".pkl",
            dir=BASE_DIR,
            delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        joblib.dump(model, temporary_path)

        os.replace(temporary_path, MODEL_PATH)

        print("\nAnomaly Model saved successfully!")
        return True

    except Exception as exc:
        print("Error: Unable to save anomaly model:", exc)
        return False

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def train_model():
    dataset = load_data()

    if dataset is None:
        print("Training cancelled. Existing model unchanged.")
        return

    X, y_true = dataset

    try:
        model = IsolationForest(
            n_estimators=100,
            contamination=0.04,
            random_state=42
        )

        model.fit(X)

        predictions = model.predict(X)

        y_pred = (predictions == -1).astype(int)

        scores = model.decision_function(X)

        if not np.all(np.isfinite(scores)):
            print("Error: Invalid anomaly scores.")
            print("Existing model unchanged.")
            return

        precision = precision_score(
            y_true,
            y_pred,
            zero_division=0
        )

        recall = recall_score(
            y_true,
            y_pred,
            zero_division=0
        )

        f1 = f1_score(
            y_true,
            y_pred,
            zero_division=0
        )

    except Exception as exc:
        print("Error: Isolation Forest training failed:", exc)
        print("Existing model unchanged.")
        return

    print("\nIsolation Forest Training Complete!")
    print("----------------------------------")
    print("Total transactions:", len(X))
    print("Detected anomalies:", int(np.sum(y_pred)))

    print("\nDemo Dataset Evaluation")
    print("Precision:", round(float(precision), 3))
    print("Recall:", round(float(recall), 3))
    print("F1 Score:", round(float(f1), 3))

    if save_model_safely(model):
        print("\nData Source: Synthetic Demo")
        print("Evaluation: Training dataset only")
        print("Training Complete!")


if __name__ == "__main__":
    train_model()

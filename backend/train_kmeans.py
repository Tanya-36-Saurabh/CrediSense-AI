
import csv
import math
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score


BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "demo_monthly_spending.csv"
MODEL_PATH = BASE_DIR / "kmeans_model.pkl"

MIN_SAMPLES = 6
N_CLUSTERS = 3


def load_data():
    if not DATA_PATH.is_file():
        print("Error: demo_monthly_spending.csv not found!")
        return None

    spending = []

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

            if "total_spending" not in reader.fieldnames:
                print("Error: total_spending column is missing.")
                return None

            for line_number, row in enumerate(reader, start=2):
                try:
                    amount = float(row["total_spending"])

                    if not math.isfinite(amount) or amount < 0:
                        raise ValueError("Invalid spending amount")

                    spending.append(amount)

                except (ValueError, TypeError, KeyError):
                    print(
                        f"Error: Invalid spending at CSV line {line_number}."
                    )
                    return None

    except (OSError, csv.Error) as exc:
        print("Error: Unable to read dataset:", exc)
        return None

    if len(spending) < MIN_SAMPLES:
        print(
            f"Error: At least {MIN_SAMPLES} records are required."
        )
        return None

    if len(set(spending)) < N_CLUSTERS:
        print(
            "Error: At least 3 distinct spending values are required."
        )
        return None

    X = np.array(spending, dtype=float).reshape(-1, 1)

    print("Total spending records:", len(spending))
    print("Dataset validation: PASS")

    return X


def save_model_safely(saved_data):
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="kmeans_",
            suffix=".pkl",
            dir=BASE_DIR,
            delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        joblib.dump(saved_data, temporary_path)

        # Replace existing model only after saving succeeds.
        os.replace(temporary_path, MODEL_PATH)

        print("\nK-Means Model saved successfully!")
        return True

    except Exception as exc:
        print("Error: Unable to save K-Means model:", exc)
        return False

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def train_kmeans():
    X = load_data()

    if X is None:
        print("Training cancelled. Existing model unchanged.")
        return

    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = KMeans(
            n_clusters=N_CLUSTERS,
            random_state=42,
            n_init=10
        )

        labels = model.fit_predict(X_scaled)

        if len(set(labels)) != N_CLUSTERS:
            print("Error: Model did not produce 3 distinct clusters.")
            print("Existing model unchanged.")
            return

        score = silhouette_score(X_scaled, labels)

        if not math.isfinite(score):
            print("Error: Invalid Silhouette Score.")
            print("Existing model unchanged.")
            return

        centers = scaler.inverse_transform(
            model.cluster_centers_
        ).flatten()

        if not np.all(np.isfinite(centers)):
            print("Error: Invalid cluster centers.")
            print("Existing model unchanged.")
            return

        sorted_clusters = np.argsort(centers)

        cluster_names = {}

        spending_labels = [
            "Low Spending",
            "Medium Spending",
            "High Spending"
        ]

        for index, cluster_id in enumerate(sorted_clusters):
            cluster_names[int(cluster_id)] = spending_labels[index]

        saved_data = {
            "model": model,
            "scaler": scaler,
            "cluster_names": cluster_names,
            "data_source": "synthetic_demo"
        }

    except Exception as exc:
        print("Error: K-Means training failed:", exc)
        print("Existing model unchanged.")
        return

    print("\nK-Means Training Complete!")
    print("Silhouette Score:", round(score, 3))

    for cluster_id, center in enumerate(centers):
        print(
            cluster_names[cluster_id],
            "- Average Spending: Rs.",
            round(float(center), 2)
        )

    if save_model_safely(saved_data):
        print("Data Source: Synthetic Demo")
        print("Training Complete!")


if __name__ == "__main__":
    train_kmeans()


import csv
from pathlib import Path

import numpy as np
import joblib

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "demo_monthly_spending.csv"
MODEL_PATH = BASE_DIR / "kmeans_model.pkl"


def train_kmeans():
    spending = []

    with open(DATA_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            spending.append(float(row["total_spending"]))

    X = np.array(spending).reshape(-1, 1)

    if len(X) < 6:
        print("Not enough data for clustering.")
        return

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = KMeans(
        n_clusters=3,
        random_state=42,
        n_init=10
    )

    labels = model.fit_predict(X_scaled)

    score = silhouette_score(X_scaled, labels)

    centers = scaler.inverse_transform(
        model.cluster_centers_
    ).flatten()

    sorted_clusters = np.argsort(centers)

    cluster_names = {}

    for index, cluster_id in enumerate(sorted_clusters):
        cluster_names[int(cluster_id)] = [
            "Low Spending",
            "Medium Spending",
            "High Spending"
        ][index]

    print("K-Means Training Complete!")
    print("Silhouette Score:", round(score, 3))

    for cluster_id, center in enumerate(centers):
        print(
            cluster_names[cluster_id],
            "- Average Spending: Rs.",
            round(center, 2)
        )

    joblib.dump(
        {
            "model": model,
            "scaler": scaler,
            "cluster_names": cluster_names,
            "data_source": "synthetic_demo"
        },
        MODEL_PATH
    )

    print("K-Means Model saved successfully!")


if __name__ == "__main__":
    train_kmeans()

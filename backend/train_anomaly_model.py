
import pandas as pd
import joblib
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "demo_anomaly_transactions.csv"
MODEL_PATH = BASE_DIR / "anomaly_model.pkl"

df = pd.read_csv(DATA_PATH)

X = df[["amount"]]
y_true = df["is_demo_anomaly"]

model = IsolationForest(
    n_estimators=100,
    contamination=0.04,
    random_state=42
)

model.fit(X)

predictions = model.predict(X)
y_pred = (predictions == -1).astype(int)

print("Isolation Forest Training Complete!")
print("Total transactions:", len(df))
print("Detected anomalies:", sum(y_pred))

print("\nDemo Dataset Evaluation")
print("Precision:", round(precision_score(y_true, y_pred, zero_division=0), 3))
print("Recall:", round(recall_score(y_true, y_pred, zero_division=0), 3))
print("F1 Score:", round(f1_score(y_true, y_pred, zero_division=0), 3))

joblib.dump(model, MODEL_PATH)

print("\nModel saved successfully!")

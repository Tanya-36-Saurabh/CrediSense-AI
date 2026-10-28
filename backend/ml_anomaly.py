
from pathlib import Path

import joblib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "anomaly_model.pkl"


class TransactionInput(BaseModel):
    amount: float = Field(gt=0)


@router.post("/detect-anomaly")
def detect_anomaly(transaction: TransactionInput):
    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Anomaly model is not trained yet"
        )

    model = joblib.load(MODEL_PATH)

    prediction = model.predict([[transaction.amount]])[0]
    score = float(model.decision_function([[transaction.amount]])[0])

    is_anomaly = prediction == -1

    return {
        "amount": transaction.amount,
        "is_anomaly": bool(is_anomaly),
        "status": "Unusual Transaction" if is_anomaly else "Normal Transaction",
        "anomaly_score": round(score, 4),
        "model": "Isolation Forest",
        "data_source": "synthetic_demo",
        "prediction_status": "demo_only"
    }


from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user


router = APIRouter(
    prefix="/api/ml",
    tags=["Machine Learning"]
)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "anomaly_model.pkl"


class TransactionInput(BaseModel):
    amount: float = Field(
        gt=0,
        allow_inf_nan=False
    )


@router.post("/detect-anomaly")
def detect_anomaly(
    transaction: TransactionInput,
    current_user=Depends(get_current_user)
):
    if not MODEL_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Anomaly model is not trained yet"
        )

    try:
        model = joblib.load(MODEL_PATH)

        features = np.array(
            [[transaction.amount]],
            dtype=float
        )

        prediction = int(
            model.predict(features)[0]
        )

        score = float(
            model.decision_function(features)[0]
        )

        if not np.isfinite(score):
            raise ValueError("Invalid anomaly score")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to detect transaction anomaly"
        )

    is_anomaly = prediction == -1

    return {
        "amount": transaction.amount,
        "is_anomaly": is_anomaly,
        "status": (
            "Unusual Transaction"
            if is_anomaly
            else "Normal Transaction"
        ),
        "anomaly_score": round(score, 4),
        "model": "Isolation Forest",
        "data_source": "synthetic_demo",
        "prediction_status": "demo_only"
    }

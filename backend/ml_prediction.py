
import csv
from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user


router = APIRouter(
    prefix="/api/ml",
    tags=["Machine Learning"]
)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "random_forest_model.pkl"
DATA_PATH = BASE_DIR / "demo_monthly_spending.csv"


@router.get("/predict-spending")
def predict_spending(
    current_user=Depends(get_current_user)
):
    if not MODEL_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="ML model not trained yet"
        )

    if not DATA_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Training data not found"
        )

    try:
        with open(
            DATA_PATH,
            newline="",
            encoding="utf-8"
        ) as file:
            rows = list(csv.DictReader(file))

    except (OSError, csv.Error):
        raise HTTPException(
            status_code=503,
            detail="Unable to read training data"
        )

    if len(rows) < 3:
        raise HTTPException(
            status_code=400,
            detail="At least 3 months of data required"
        )

    try:
        spending = [
            float(row["total_spending"])
            for row in rows[-3:]
        ]

        if not all(np.isfinite(value) for value in spending):
            raise ValueError("Non-finite spending value")

    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid spending data"
        )

    features = np.array(
        [[spending[-1], spending[-2], spending[-3]]]
    )

    try:
        model = joblib.load(MODEL_PATH)

        prediction = float(
            model.predict(features)[0]
        )

        if not np.isfinite(prediction):
            raise ValueError("Invalid prediction")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to generate prediction"
        )

    return {
        "predicted_spending": round(
            max(0, prediction), 2
        ),
        "currency": "INR",
        "model": "Random Forest Regressor",
        "data_source": "synthetic_demo",
        "historical_months": len(rows),
        "prediction_status": "demo_only"
    }


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
MODEL_PATH = BASE_DIR / "kmeans_model.pkl"


class SpendingInput(BaseModel):
    monthly_spending: float = Field(
        ge=0,
        allow_inf_nan=False
    )


@router.post("/classify-spending")
def classify_spending(
    data: SpendingInput,
    current_user=Depends(get_current_user)
):
    if not MODEL_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="K-Means model not trained yet"
        )

    try:
        saved_data = joblib.load(MODEL_PATH)

        model = saved_data["model"]
        scaler = saved_data["scaler"]
        cluster_names = saved_data["cluster_names"]

        features = np.array(
            [[data.monthly_spending]],
            dtype=float
        )

        scaled_features = scaler.transform(features)

        cluster_id = int(
            model.predict(scaled_features)[0]
        )

        spending_pattern = cluster_names[cluster_id]

    except (
        KeyError,
        IndexError,
        ValueError,
        TypeError,
        AttributeError
    ):
        raise HTTPException(
            status_code=500,
            detail="Invalid K-Means model data"
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to classify spending"
        )

    return {
        "monthly_spending": data.monthly_spending,
        "spending_pattern": spending_pattern,
        "cluster_id": cluster_id,
        "model": "K-Means Clustering",
        "data_source": "synthetic_demo",
        "prediction_status": "demo_only"
    }

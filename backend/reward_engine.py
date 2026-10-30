
"""CrediSense AI 2.0 - Reward recommendation engine."""

from pathlib import Path
import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v2", tags=["Rewards v2"])

DB_PATH = Path(__file__).resolve().parent / "credisense.db"


class PurchaseRequestV2(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    merchant: Optional[str] = Field(default=None, max_length=100)


def get_connection():
    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="Database not initialized"
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.post("/recommend-card")
def recommend_card_v2(purchase: PurchaseRequestV2):
    category = purchase.category.strip()

    if not category:
        raise HTTPException(
            status_code=422,
            detail="Category cannot be blank"
        )

    with get_connection() as conn:
        try:
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(reward_catalog)"
                )
            }

            required_columns = {
                "max_cashback",
                "min_transaction",
                "eligible_merchant"
            }

            if not required_columns.issubset(columns):
                raise HTTPException(
                    status_code=503,
                    detail="Reward database migration not applied"
                )

            rows = conn.execute("""
                SELECT
                    c.id AS card_id,
                    c.bank_name,
                    c.card_name,
                    c.credit_limit,
                    c.outstanding,
                    r.reward_percent,
                    r.max_cashback,
                    r.min_transaction,
                    r.eligible_merchant
                FROM cards AS c
                JOIN reward_catalog AS r
                    ON LOWER(TRIM(c.bank_name)) =
                       LOWER(TRIM(r.bank_name))
                    AND LOWER(TRIM(c.card_name)) =
                        LOWER(TRIM(r.card_name))
                WHERE LOWER(TRIM(r.category)) = LOWER(?)
            """, (category,)).fetchall()

        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503,
                detail="Reward data unavailable"
            ) from exc

    recommendations = []

    for row in rows:
        available = (
            float(row["credit_limit"])
            - float(row["outstanding"])
        )

        minimum = float(row["min_transaction"])

        if purchase.amount < minimum:
            continue

        eligible_merchant = row["eligible_merchant"]

        if eligible_merchant is not None:
            if not purchase.merchant:
                continue

            if (
                purchase.merchant.strip().casefold()
                != eligible_merchant.strip().casefold()
            ):
                continue

        rate = float(row["reward_percent"])
        cap = row["max_cashback"]

        if available < purchase.amount:
            continue

        if not (0 <= rate <= 100):
            continue

        if cap is not None and float(cap) < 0:
            continue

        raw_reward = purchase.amount * rate / 100

        estimate = (
            min(raw_reward, float(cap))
            if cap is not None
            else raw_reward
        )

        recommendations.append({
            "card_id": row["card_id"],
            "bank_name": row["bank_name"],
            "card_name": row["card_name"],
            "reward_percent": rate,
            "max_cashback": cap,
            "min_transaction": minimum,
            "eligible_merchant": eligible_merchant,
            "estimated_cashback": round(estimate, 2),
            "available_limit": round(available, 2),
            "policy_status": "demo/unverified"
        })

    recommendations.sort(
        key=lambda item: (
            -item["estimated_cashback"],
            -item["available_limit"],
            item["card_id"]
        )
    )

    return {
        "category": category.title(),
        "purchase_amount": purchase.amount,
        "best_card": (
            recommendations[0]
            if recommendations
            else None
        ),
        "recommendations": recommendations,
        "note": (
            "Demo reward rates/caps only; "
            "real benefits depend on issuer terms."
        )
    }


@router.get("/reward-catalog")
def reward_catalog_v2():
    with get_connection() as conn:
        try:
            rows = conn.execute("""
                SELECT
                    bank_name,
                    card_name,
                    category,
                    reward_percent,
                    max_cashback,
                    min_transaction,
                    eligible_merchant
                FROM reward_catalog
                ORDER BY bank_name, card_name, category
            """).fetchall()

        except sqlite3.Error as exc:
            raise HTTPException(
                status_code=503,
                detail="Reward catalog unavailable"
            ) from exc

    return {
        "total_rewards": len(rows),
        "rewards": [dict(row) for row in rows],
        "policy_status": "demo/unverified"
    }


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/insights", tags=["Financial Insights"])


class SpendingInput(BaseModel):
    current_month: float = Field(ge=0)
    previous_month: float = Field(ge=0)


@router.post("/monthly")
def monthly_insights(data: SpendingInput):
    current = data.current_month
    previous = data.previous_month

    difference = round(current - previous, 2)

    if previous == 0:
        percentage_change = None
        if current > 0:
            insight = (
                "Spending has started this month. "
                "There is no previous-month spending to compare."
            )
        else:
            insight = "No spending recorded in either month."

    else:
        percentage_change = round(
            (difference / previous) * 100, 2
        )

        if percentage_change > 10:
            insight = (
                "Your spending increased by more than 10%. "
                "Review your major expense categories."
            )

        elif percentage_change < -10:
            insight = (
                "Your spending decreased by more than 10%. "
                "Review which categories contributed to the reduction."
            )

        else:
            insight = (
                "Your spending remained relatively stable "
                "compared with the previous month."
            )

    return {
        "current_month_spending": current,
        "previous_month_spending": previous,
        "difference": difference,
        "percentage_change": percentage_change,
        "insight": insight,
        "analysis_type": "rule_based",
        "currency": "INR"
    }

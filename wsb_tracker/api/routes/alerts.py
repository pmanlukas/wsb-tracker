"""Alert-related API routes."""

from fastapi import APIRouter, HTTPException, Query

from wsb_tracker.api.schemas import AlertResponse, AlertsResponse
from wsb_tracker.tracker import WSBTracker

router = APIRouter()


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    include_acknowledged: bool = Query(False, description="Include acknowledged alerts"),
    limit: int = Query(50, ge=1, le=200, description="Maximum alerts to return"),
) -> AlertsResponse:
    """Get alerts.

    By default returns only unacknowledged alerts.
    """
    tracker = WSBTracker()

    if include_acknowledged:
        # Get all recent alerts (would need to implement this method)
        alerts = tracker.get_alerts()
    else:
        alerts = tracker.get_alerts()  # Returns unacknowledged by default

    # Limit results
    alerts = alerts[:limit]

    alert_responses = [
        AlertResponse(
            id=a.id,
            ticker=a.ticker,
            alert_type=a.alert_type,
            message=a.message,
            heat_score=a.heat_score,
            sentiment=a.sentiment,
            triggered_at=a.triggered_at,
            acknowledged=a.acknowledged,
        )
        for a in alerts
    ]

    unack_count = sum(1 for a in alerts if not a.acknowledged)

    return AlertsResponse(
        alerts=alert_responses,
        total=len(alert_responses),
        unacknowledged=unack_count,
    )


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str) -> dict:
    """Acknowledge an alert.

    Accepts either full ID or first 8 characters.
    """
    tracker = WSBTracker()

    # Find alert by partial ID
    alerts = tracker.get_alerts()
    for alert in alerts:
        if alert.id == alert_id or alert.id.startswith(alert_id):
            tracker.acknowledge_alert(alert.id)
            return {
                "status": "acknowledged",
                "alert_id": alert.id,
                "ticker": alert.ticker,
            }

    raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")


@router.post("/alerts/ack-all")
async def acknowledge_all_alerts() -> dict:
    """Acknowledge all pending alerts."""
    tracker = WSBTracker()
    count = tracker.acknowledge_all_alerts()

    return {
        "status": "acknowledged",
        "count": count,
    }

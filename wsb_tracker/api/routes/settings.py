"""Settings API routes for scan configuration."""

from fastapi import APIRouter, HTTPException

from wsb_tracker.api.schemas import ScanSettingsRequest, ScanSettingsResponse
from wsb_tracker.runtime_settings import (
    RuntimeSettings,
    get_runtime_settings,
    save_runtime_settings,
    reset_runtime_settings,
    invalidate_settings_cache,
)

router = APIRouter()


@router.get("/settings/scan", response_model=ScanSettingsResponse)
async def get_scan_settings() -> ScanSettingsResponse:
    """Get current scan settings."""
    settings = get_runtime_settings()

    return ScanSettingsResponse(
        subreddits=settings.subreddits,
        scan_limit=settings.scan_limit,
        request_delay=settings.request_delay,
        min_score=settings.min_score,
        scan_sort=settings.scan_sort,
    )


@router.put("/settings/scan", response_model=ScanSettingsResponse)
async def update_scan_settings(request: ScanSettingsRequest) -> ScanSettingsResponse:
    """Update scan settings. Changes apply immediately to next scan."""
    # Validate subreddits
    if not request.subreddits:
        raise HTTPException(status_code=400, detail="At least one subreddit is required")

    # Clean up subreddit names
    subreddits = [s.strip().lower() for s in request.subreddits if s.strip()]
    if not subreddits:
        raise HTTPException(status_code=400, detail="At least one valid subreddit is required")

    # Validate scan_sort
    valid_sorts = ["hot", "new", "rising", "top"]
    if request.scan_sort not in valid_sorts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scan_sort. Must be one of: {', '.join(valid_sorts)}",
        )

    # Validate ranges
    if not (10 <= request.scan_limit <= 500):
        raise HTTPException(status_code=400, detail="scan_limit must be between 10 and 500")
    if not (0.5 <= request.request_delay <= 10.0):
        raise HTTPException(status_code=400, detail="request_delay must be between 0.5 and 10.0")
    if request.min_score < 0:
        raise HTTPException(status_code=400, detail="min_score must be non-negative")

    settings = RuntimeSettings(
        subreddits=subreddits,
        scan_limit=request.scan_limit,
        request_delay=request.request_delay,
        min_score=request.min_score,
        scan_sort=request.scan_sort,
    )
    save_runtime_settings(settings)
    invalidate_settings_cache()

    return ScanSettingsResponse(
        subreddits=settings.subreddits,
        scan_limit=settings.scan_limit,
        request_delay=settings.request_delay,
        min_score=settings.min_score,
        scan_sort=settings.scan_sort,
    )


@router.post("/settings/scan/reset", response_model=ScanSettingsResponse)
async def reset_settings() -> ScanSettingsResponse:
    """Reset scan settings to defaults from config."""
    settings = reset_runtime_settings()
    invalidate_settings_cache()

    return ScanSettingsResponse(
        subreddits=settings.subreddits,
        scan_limit=settings.scan_limit,
        request_delay=settings.request_delay,
        min_score=settings.min_score,
        scan_sort=settings.scan_sort,
    )

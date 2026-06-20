"""배치 스케줄러 관리 API."""
from fastapi import APIRouter

from app.services import batch_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
def get_status() -> dict:
    """스케줄러 상태 + 마지막 실행 결과."""
    return batch_scheduler.status()


@router.post("/run")
def trigger_run() -> dict:
    """배치 즉시 실행 (수동 트리거). KRX_OPEN_API_KEY 미설정 시 skipped."""
    return batch_scheduler.run_now()

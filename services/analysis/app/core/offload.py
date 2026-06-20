"""torch 학습 오프로드 — 이벤트 루프 비블로킹.

문제: `async def` 핸들러 안에서 동기 torch 학습(수초)을 직접 호출하면 uvicorn
워커의 이벤트 루프가 그동안 정지 → 동시 요청·/health·WS 피드가 전부 굶는다.
스레드풀 오프로드는 macOS 에서 torch+OpenMP 워커스레드 segfault 위험.

해결: 기본은 **별도 프로세스**(ProcessPoolExecutor)로 학습을 격리 실행 →
루프 비블로킹 + torch 상태 프로세스 격리. 단일 사용·테스트(mock 주입·결정성)
환경은 `ANALYSIS_INPROC_TRAIN=1` 로 인프로세스(메인 스레드) 실행.
"""
import asyncio
import importlib
import os
from concurrent.futures import ProcessPoolExecutor

_EXECUTOR: ProcessPoolExecutor | None = None


def _executor() -> ProcessPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ProcessPoolExecutor(max_workers=int(os.getenv("BACKTEST_WORKERS", "2")))
    return _EXECUTOR


def _call(module: str, func: str, kwargs: dict) -> dict:
    """프로세스 워커 진입점(피클 가능) — 모듈 import 후 함수 호출."""
    return getattr(importlib.import_module(module), func)(**kwargs)


async def run_training(module: str, func: str, **kwargs) -> dict:
    """torch 학습 함수를 비블로킹 실행.

    ANALYSIS_INPROC_TRAIN=1 → 인프로세스(메인 스레드, 테스트/로컬 단일 사용).
    그 외 → ProcessPoolExecutor(루프 비블로킹 + torch 격리).
    ValueError 등 예외는 부모로 그대로 전파(피클 후 재발생).
    """
    if os.getenv("ANALYSIS_INPROC_TRAIN") == "1":
        return _call(module, func, kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor(), _call, module, func, kwargs)

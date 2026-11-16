"""Documented HD billing and job-poll semantics for offline tests."""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping


CHINA_RATES = {"1080p": 0.04, "2k": 0.08, "4k": 0.12}
OVERSEAS_TARGET_MULTIPLIER = {"1080p": 1, "2k": 2, "4k": 3}


def billable_seconds(duration_seconds: float) -> int:
    """Regional HD contracts: max(15, ceil(source seconds))."""
    return max(15, math.ceil(duration_seconds))


def fps_multiplier(fps: float) -> int:
    """Double only when average FPS is greater than 30."""
    return 2 if fps > 30 else 1


def china_hd_cost(duration_seconds: float, fps: float, target: str, discount: float = 1.0) -> float:
    return (
        billable_seconds(duration_seconds)
        * CHINA_RATES[target]
        * fps_multiplier(fps)
        * discount
    )


def overseas_hd_cost(
    duration_seconds: float,
    fps: float,
    target: str,
    all_area_rate: float,
    discount: float = 1.0,
) -> float:
    """Use a caller-supplied all_area rate from a balance response; not a published list price."""
    return (
        billable_seconds(duration_seconds)
        * all_area_rate
        * OVERSEAS_TARGET_MULTIPLIER[target]
        * fps_multiplier(fps)
        * discount
    )


class JobFailedError(RuntimeError):
    def __init__(self, job_id: str, job: Mapping[str, Any]):
        self.job_id = job_id
        self.job = job
        super().__init__(f"Job {job_id} ended with status {job.get('status')}")


class JobTimeoutError(RuntimeError):
    def __init__(self, job_id: str, job: Mapping[str, Any] | None):
        self.job_id = job_id
        self.job = job
        status = job.get("status") if job else None
        super().__init__(
            f"Job poll timed out; job still pending. JOB_ID={job_id} status={status}. "
            "Keep this ID and query later. The server job was not canceled."
        )


class JobQueryError(RuntimeError):
    pass


def retry_after_seconds(headers: Mapping[str, str] | None, default: float = 5.0, cap: float = 60.0) -> float:
    if not headers:
        return default
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return default
    try:
        return min(max(float(raw), 0), cap)
    except ValueError:
        return default


def poll_and_download(
    job_id: str,
    get_job: Callable[[str], tuple[int, Mapping[str, Any], Mapping[str, str] | None]],
    download: Callable[[str, str], None],
    output_path: str,
    *,
    max_attempts: int = 360,
    interval: float = 5.0,
    sleep: Callable[[float], None] = lambda _seconds: None,
    retry_cap: float = 60.0,
) -> Mapping[str, Any]:
    """Poll until success, terminal failure, or timeout. Never cancels the server job."""
    job: Mapping[str, Any] | None = None
    for _ in range(max_attempts):
        status_code, body, headers = get_job(job_id)
        if status_code == 429:
            sleep(retry_after_seconds(headers, default=interval, cap=retry_cap))
            continue
        if status_code != 200:
            raise JobQueryError(f"Job query failed HTTP {status_code} JOB_ID={job_id}")
        job = body
        status = body.get("status")
        if status == "succeeded":
            download(body["result"]["url"], output_path)
            return body
        if status in {"failed", "canceled"}:
            raise JobFailedError(job_id, body)
        sleep(interval)
    raise JobTimeoutError(job_id, job)

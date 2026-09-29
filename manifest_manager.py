"""
Observability and run artifact management module for daily briefing.
Manages artifacts/run.log and artifacts/manifest.json according to G4 schema.
Provides typed domain state contracts for Search, Gemini, and Publishing.
"""

from __future__ import annotations

import os
import re
import json
import time
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Sequence, Tuple, Union


# KST (UTC+9)
KST: timezone = timezone(timedelta(hours=9))


# ==========================================
# Typed State Contracts (§5)
# ==========================================

class SearchStatus(str, Enum):
    """OpenAlex 및 학술 검색 상태 계약 (§5.1)"""
    SEARCH_OK = "SEARCH_OK"
    SEARCH_GENUINE_EMPTY = "SEARCH_GENUINE_EMPTY"
    OPENALEX_RATE_LIMITED = "OPENALEX_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"


class GeminiOutcome(str, Enum):
    """Gemini 시도 결과 분류 (§5.2)"""
    SUCCESS = "SUCCESS"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    OUTPUT_TOO_SHORT = "OUTPUT_TOO_SHORT"
    OUTPUT_TOO_LONG = "OUTPUT_TOO_LONG"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class PublishStatus(str, Enum):
    """전체 실행 및 게시 상태 계약 (§5.3)"""
    PUBLISHED_TEXT_AND_IMAGES = "PUBLISHED_TEXT_AND_IMAGES"
    PUBLISHED_TEXT_IMAGE_PARTIAL = "PUBLISHED_TEXT_IMAGE_PARTIAL"
    DEGRADED_PROVIDER_FAILURE = "DEGRADED_PROVIDER_FAILURE"
    PUBLISH_FAILED = "PUBLISH_FAILED"
    GENERATE_FAILED = "GENERATE_FAILED"


@dataclass(frozen=True)
class GeminiAttemptRecord:
    """Gemini 시도별 진단 기록"""
    model: str
    attempt_type: str  # "FULL" | "CONDENSE"
    outcome: str
    char_count: Optional[int]
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "attempt_type": self.attempt_type,
            "outcome": self.outcome,
            "char_count": self.char_count,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass
class AcademicSearchResult:
    """학술 검색 결과 및 메트릭 구조체 (§6.2)"""
    papers: List[Any]
    status: SearchStatus
    query_metrics: Dict[str, Any] = field(default_factory=dict)
    rejection_counts: Dict[str, int] = field(default_factory=dict)
    provider_failures: List[str] = field(default_factory=list)
    degraded: bool = False
    polite_pool_configured: bool = False


@dataclass(frozen=True)
class InfographicSpec:
    """G5 인포그래픽 데이터 계약 (§5.4)"""
    infographic_id: str
    title: str
    chart_type: str
    labels: List[str]
    values: List[float]
    unit: str
    source_ids: List[str]
    caption: str
    alt_text: str

    ALLOWLIST_CHART_TYPES = ("bar", "horizontal_bar", "line")

    def validate(self) -> None:
        """InfographicSpec 검증 규칙 실행"""
        if not self.infographic_id or not self.infographic_id.strip():
            raise ValueError("infographic_id는 비어 있을 수 없습니다.")
        if not self.title or not self.title.strip():
            raise ValueError("title은 비어 있을 수 없습니다.")
        if self.chart_type not in self.ALLOWLIST_CHART_TYPES:
            raise ValueError(f"chart_type '{self.chart_type}'은 허용 목록에 없습니다: {self.ALLOWLIST_CHART_TYPES}")
        if len(self.labels) == 0 or len(self.values) == 0:
            raise ValueError("labels와 values는 최소 1개 이상이어야 합니다.")
        if len(self.labels) != len(self.values):
            raise ValueError(f"labels({len(self.labels)})와 values({len(self.values)})의 길이가 일치하지 않습니다.")
        for v in self.values:
            import math
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"유효하지 않은 수치 데이터(NaN 또는 Infinity): {v}")
        if not self.source_ids:
            raise ValueError("모든 차트 데이터는 검증된 source_ids와 연계되어야 합니다.")
        if not self.caption or not self.caption.strip():
            raise ValueError("caption은 비어 있을 수 없습니다.")
        if not self.alt_text or not self.alt_text.strip():
            raise ValueError("alt_text는 비어 있을 수 없습니다.")


# ==========================================
# Secret Redaction (§3)
# ==========================================

SENSITIVE_PATTERNS = [
    re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]{10,}', re.IGNORECASE),
    re.compile(r'(AIzaSy)[A-Za-z0-9_\-]{30,}', re.IGNORECASE),
    re.compile(r'(secret_)[A-Za-z0-9_\-]{20,}', re.IGNORECASE),
    re.compile(r'(ntn_)[A-Za-z0-9_\-]{20,}', re.IGNORECASE),
    re.compile(r'(https://hooks\.slack\.com/services/)[A-Za-z0-9/\-_]+', re.IGNORECASE),
    re.compile(r'(mailto:)[^@\s]+@[^@\s]+\.[a-zA-Z0-9]+', re.IGNORECASE),
]

def redact_secrets(text: str) -> str:
    """Mask known sensitive patterns from logs, manifests, and error strings."""
    if not isinstance(text, str):
        return text
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(r'\1[REDACTED]', result)
    return result


def hash_page_id(page_id: Optional[str]) -> Optional[str]:
    """Never expose raw page ID; produce a short deterministic one-way hash."""
    if not page_id:
        return None
    return hashlib.sha256(page_id.encode('utf-8')).hexdigest()[:12]


# ==========================================
# Manifest Manager (G4)
# ==========================================

class ManifestManager:
    """
    artifacts/run.log 및 artifacts/manifest.json 생명주기를 총괄하는 관리자.
    어떤 단계에서 실패하더라도 진단 가능한 상태와 로그가 파일로 보존되도록 보장한다.
    """
    def __init__(self, artifacts_dir: str = "artifacts") -> None:
        self.artifacts_dir = artifacts_dir
        self.log_path = os.path.join(artifacts_dir, "run.log")
        self.manifest_path = os.path.join(artifacts_dir, "manifest.json")
        self.manifest_data: Dict[str, Any] = {}
        self.is_initialized = False

    def initialize(
        self,
        decision_id: str,
        topic: str,
        run_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
    ) -> None:
        """실행 시작 직후 외부 API 호출 전에 호출되어 스켈레톤 파일들을 디스크에 생성."""
        os.makedirs(self.artifacts_dir, exist_ok=True)
        now_iso = datetime.now(KST).isoformat()

        self.manifest_data = {
            "schema_version": 1,
            "run": {
                "run_id": run_id,
                "decision_id": decision_id,
                "commit_sha": commit_sha,
                "topic": topic,
                "started_at": now_iso,
                "finished_at": None,
                "status": "RUNNING",
            },
            "academic_search": {
                "status": "NOT_STARTED",
                "query_count": 0,
                "request_count": 0,
                "rate_limited_count": 0,
                "success_count": 0,
                "eligible_paper_count": 0,
                "polite_pool_configured": False,
            },
            "gemini_attempts": [],
            "report": {
                "body_length": None,
                "quality_state": None,
            },
            "notion": {
                "status": "NOT_STARTED",
                "page_id_hash": None,
                "expected_image_count": 0,
                "uploaded_image_count": 0,
                "read_back_image_count": 0,
            },
            "infographics": [],
            "failure": None,
        }

        self._atomic_write_manifest()
        self.is_initialized = True
        self.log(
            f"Run initialized: decision_id={decision_id}, run_id={run_id}, topic='{topic}'",
            stage="INITIALIZE"
        )

    def log(self, message: str, level: str = "INFO", stage: Optional[str] = None) -> None:
        """사람이 읽을 수 있는 타임스탬프 로그를 run.log에 기록하고 콘솔에 출력."""
        os.makedirs(self.artifacts_dir, exist_ok=True)
        now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')
        stage_tag = f" [{stage}]" if stage else ""
        safe_msg = redact_secrets(message)
        line = f"[{now_str}] [{level}]{stage_tag} {safe_msg}\n"

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def update_academic_search(
        self,
        status: str,
        query_count: int,
        request_count: int,
        rate_limited_count: int,
        success_count: int,
        eligible_paper_count: int,
        polite_pool_configured: bool = False,
    ) -> None:
        """학술 검색 단계 지표 반영"""
        if not self.is_initialized:
            return
        self.manifest_data["academic_search"] = {
            "status": status,
            "query_count": query_count,
            "request_count": request_count,
            "rate_limited_count": rate_limited_count,
            "success_count": success_count,
            "eligible_paper_count": eligible_paper_count,
            "polite_pool_configured": polite_pool_configured,
        }
        self._atomic_write_manifest()

    def record_gemini_attempt(
        self,
        model: str,
        attempt_type: str,
        outcome: str,
        char_count: Optional[int],
        elapsed_seconds: float,
    ) -> None:
        """Gemini 시도 기록 추가"""
        if not self.is_initialized:
            return
        record = GeminiAttemptRecord(
            model=model,
            attempt_type=attempt_type,
            outcome=outcome,
            char_count=char_count,
            elapsed_seconds=elapsed_seconds,
        )
        self.manifest_data["gemini_attempts"].append(record.to_dict())
        self._atomic_write_manifest()
        self.log(
            f"Gemini attempt: model={model}, type={attempt_type}, outcome={outcome}, "
            f"chars={char_count}, elapsed={elapsed_seconds:.2f}s",
            stage="GEMINI"
        )

    def update_report(self, body_length: Optional[int], quality_state: Optional[str]) -> None:
        """생성된 리포트 메트릭 반영"""
        if not self.is_initialized:
            return
        self.manifest_data["report"] = {
            "body_length": body_length,
            "quality_state": quality_state,
        }
        self._atomic_write_manifest()

    def update_notion(
        self,
        status: str,
        page_id_hash: Optional[str] = None,
        expected_image_count: int = 0,
        uploaded_image_count: int = 0,
        read_back_image_count: int = 0,
    ) -> None:
        """Notion 게시 단계 지표 반영"""
        if not self.is_initialized:
            return
        self.manifest_data["notion"] = {
            "status": status,
            "page_id_hash": page_id_hash,
            "expected_image_count": expected_image_count,
            "uploaded_image_count": uploaded_image_count,
            "read_back_image_count": read_back_image_count,
        }
        self._atomic_write_manifest()

    def record_failure(self, stage: str, error_type: str, safe_message: str) -> None:
        """실패 발생 시 진단 정보 기록 및 상태 FAILED 전환"""
        if not self.is_initialized:
            return
        self.manifest_data["failure"] = {
            "stage": stage,
            "error_type": error_type,
            "error_message_safe": redact_secrets(safe_message),
        }
        self.manifest_data["run"]["status"] = "FAILED"
        self.manifest_data["run"]["finished_at"] = datetime.now(KST).isoformat()
        self._atomic_write_manifest()
        self.log(f"Stage [{stage}] failed: {error_type} - {safe_message}", level="ERROR", stage=stage)

    def finish(self, status: str = "SUCCESS") -> None:
        """성공 또는 종료 상태 확정"""
        if not self.is_initialized:
            return
        self.manifest_data["run"]["status"] = status
        self.manifest_data["run"]["finished_at"] = datetime.now(KST).isoformat()
        self._atomic_write_manifest()
        self.log(f"Run completed with status: {status}", stage="COMPLETION")

    def _atomic_write_manifest(self) -> None:
        """임시 파일 작성 후 교체하는 atomic write로 항상 유효한 JSON 보장"""
        temp_path = f"{self.manifest_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.manifest_path)

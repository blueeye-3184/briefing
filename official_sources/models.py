"""official_sources.models

공식 1차 자료(Official Primary Evidence) 도메인 모델 및 열거형 정의.
Codex 명세(P0_4_OFFICIAL_SOURCE_INTERFACE_TASK.md)를 준수합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping


class SourceType(str, Enum):
    STATISTICS = "statistics"
    POLICY = "policy"
    NOTICE = "notice"
    ANNOUNCEMENT = "announcement"
    GUIDANCE = "guidance"


class VerificationStatus(str, Enum):
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NOT_VERIFIED = "not_verified"


class EvidenceStatus(str, Enum):
    READY = "ready"
    SOURCE_DEFICIT = "source_deficit"


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    title: str
    publisher: str
    published_at: datetime
    effective_at: datetime | None
    retrieved_at: datetime
    url: str
    canonical_url: str
    source_type: SourceType
    evidence_excerpt: str
    content_hash: str
    verification_status: VerificationStatus
    final_domain: str
    topic_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TopicPolicy:
    topic_id: str
    day_of_week: int
    title: str
    subtopics: tuple[str, ...]
    academic_target: int
    academic_minimum: int
    official_target: int
    official_minimum: int
    freshness_days: int
    allowed_domains: tuple[str, ...]
    required_keywords: tuple[str, ...]
    excluded_keywords: tuple[str, ...] = ()
    required_sections: tuple[str, ...] = ()
    deficit_scope: str = ""


@dataclass(frozen=True)
class SourceQuery:
    topic_id: str
    keywords: tuple[str, ...]
    start_date: date
    end_date: date
    region_codes: tuple[str, ...] = ()
    limit: int = 20


@dataclass(frozen=True)
class ProviderResult:
    provider_id: str
    queries: tuple[str, ...]
    candidates: tuple[OfficialSource, ...]
    rejection_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidencePack:
    topic_id: str
    official_sources: tuple[OfficialSource, ...]
    provider_results: tuple[ProviderResult, ...]
    status: EvidenceStatus
    deficits: tuple[str, ...]
    collected_at: datetime

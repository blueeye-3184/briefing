"""official_sources.verification

공식 1차 자료 검증 게이트(OfficialSourceVerifier):
- 필수 필드 및 HTTPS 검증
- 허용 도메인 및 Publisher 정합성 검증
- 날짜 유효성, 미래 날짜 배제 및 최신성 검증
- 결정론적 SHA-256 Content Hash 계산
- Rejection Code 체계 준수
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
from official_sources.http_client import is_domain_allowed
from official_sources.models import (
    OfficialSource,
    TopicPolicy,
    VerificationStatus,
)

# 출처 도메인과 신뢰 Publisher 매핑 규칙
DOMAIN_PUBLISHER_MAP: dict[str, tuple[str, ...]] = {
    "kosis.kr": ("통계청", "KOSIS", "국가통계포털"),
    "reb.or.kr": ("한국부동산원", "R-ONE", "부동산통계정보시스템"),
    "data.go.kr": ("공공데이터포털", "행정안전부", "한국부동산원", "국토교통부", "통계청"),
    "molit.go.kr": ("국토교통부", "MOLIT"),
    "gumi.go.kr": ("구미시", "구미시청"),
    "gc.go.kr": ("김천시", "김천시청"),
    "gb.go.kr": ("경상북도", "경상북도청"),
    "iris.go.kr": ("범부처통합연구지원시스템", "IRIS", "과학기술정보통신부"),
    "kaia.re.kr": ("국토교통과학기술진흥원", "KAIA"),
}


def calculate_content_hash(title: str, excerpt: str, canonical_url: str) -> str:
    """광고·시간 등 가변 요소를 배제한 결정론적 내용 해시 계산"""
    normalized = f"{title.strip()}|{excerpt.strip()}|{canonical_url.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class OfficialSourceVerifier:
    """공식 자료의 신뢰성과 메타데이터 무결성을 검증하는 게이트웨이"""

    def verify(
        self,
        source: OfficialSource,
        policy: TopicPolicy,
        evaluation_time: datetime | None = None,
    ) -> tuple[OfficialSource, str | None]:
        """후보 자료를 검증하여 VERIFIED 또는 REJECTED 상태의 새 OfficialSource와 이유 코드 반환"""
        now = evaluation_time or datetime.now(timezone.utc)

        # 1. 필수 필드 검사
        if not source.source_id or not source.title.strip() or not source.url.strip():
            return self._reject(source, "missing_required_field")
        if not source.publisher.strip() or not source.final_domain.strip():
            return self._reject(source, "missing_required_field")

        # 2. HTTPS 프로토콜 검사
        parsed_url = urlparse(source.url)
        parsed_canonical = urlparse(source.canonical_url)
        if parsed_url.scheme.lower() != "https" or parsed_canonical.scheme.lower() != "https":
            return self._reject(source, "non_https_url")

        # 3. 도메인 allowlist 검증
        if not is_domain_allowed(parsed_url.netloc, policy.allowed_domains):
            return self._reject(source, "disallowed_domain")
        if not is_domain_allowed(source.final_domain, policy.allowed_domains):
            return self._reject(source, "redirect_domain_mismatch")

        # 4. Publisher - Domain 정합성 검증
        domain_matched = False
        for mapped_domain, valid_publishers in DOMAIN_PUBLISHER_MAP.items():
            if is_domain_allowed(source.final_domain, [mapped_domain]):
                domain_matched = True
                if not any(vp in source.publisher for vp in valid_publishers):
                    return self._reject(source, "publisher_domain_mismatch")
                break
        if not domain_matched and policy.allowed_domains:
            # 매핑에 없는 도메인은 allowlist에 있더라도 도메인명이 출처에 연관되어야 함
            if not any(domain_part in source.publisher.lower() for domain_part in source.final_domain.split(".")):
                return self._reject(source, "publisher_domain_mismatch")

        # 5. 날짜 유효성, timezone-aware, 미래 날짜 및 최신성 검사
        if not isinstance(source.published_at, datetime):
            return self._reject(source, "invalid_published_at")
        if source.published_at.tzinfo is None:
            return self._reject(source, "invalid_published_at")

        # 미래 날짜 거부
        if source.published_at > now:
            return self._reject(source, "future_published_at")

        # 최신성(freshness) 검사 (일수)
        if policy.freshness_days > 0:
            age_days = (now - source.published_at).total_seconds() / 86400.0
            if age_days > policy.freshness_days:
                return self._reject(source, "stale_source")

        # 6. Evidence excerpt 검증
        if not source.evidence_excerpt or len(source.evidence_excerpt.strip()) < 10:
            return self._reject(source, "missing_evidence_excerpt")

        # 7. 공고 상세 검증 여부 (IRIS/KAIA 등)
        if source.metadata.get("list_only_unverified", False):
            return self._reject(source, "announcement_detail_unverified")

        # 8. Content hash 무결성 계산
        computed_hash = calculate_content_hash(
            source.title, source.evidence_excerpt, source.canonical_url
        )

        verified_source = OfficialSource(
            source_id=source.source_id,
            title=source.title.strip(),
            publisher=source.publisher.strip(),
            published_at=source.published_at,
            effective_at=source.effective_at,
            retrieved_at=source.retrieved_at,
            url=source.url,
            canonical_url=source.canonical_url,
            source_type=source.source_type,
            evidence_excerpt=source.evidence_excerpt.strip(),
            content_hash=computed_hash,
            verification_status=VerificationStatus.VERIFIED,
            final_domain=source.final_domain.lower(),
            topic_id=policy.topic_id,
            metadata=source.metadata,
        )
        return verified_source, None

    @staticmethod
    def _reject(source: OfficialSource, reason: str) -> tuple[OfficialSource, str]:
        rejected_source = OfficialSource(
            source_id=source.source_id,
            title=source.title,
            publisher=source.publisher,
            published_at=source.published_at,
            effective_at=source.effective_at,
            retrieved_at=source.retrieved_at,
            url=source.url,
            canonical_url=source.canonical_url,
            source_type=source.source_type,
            evidence_excerpt=source.evidence_excerpt,
            content_hash=source.content_hash,
            verification_status=VerificationStatus.REJECTED,
            final_domain=source.final_domain,
            topic_id=source.topic_id,
            metadata={**dict(source.metadata), "rejection_reason": reason},
        )
        return rejected_source, reason

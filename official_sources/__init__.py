"""official_sources package

공식 1차 자료 수집 및 검증 바운디드 컨텍스트 (P0-4):
- 도메인 모델: EvidencePack, OfficialSource, TopicPolicy, SourceQuery, ProviderResult, SourceType, VerificationStatus, EvidenceStatus
- 정책 레지스트리: TopicPolicyRegistry
- 검증 게이트: OfficialSourceVerifier
- 서비스: OfficialEvidenceService
- 안전 HTTP 클라이언트: SafeHttpClient
"""

from official_sources.http_client import SafeHttpClient, is_domain_allowed, sanitize_url
from official_sources.models import (
    EvidencePack,
    EvidenceStatus,
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import HttpTransport, OfficialSourceProvider
from official_sources.registry import TopicPolicyRegistry
from official_sources.service import OfficialEvidenceService
from official_sources.verification import OfficialSourceVerifier

__all__ = [
    "EvidencePack",
    "EvidenceStatus",
    "HttpTransport",
    "OfficialEvidenceService",
    "OfficialSource",
    "OfficialSourceProvider",
    "OfficialSourceVerifier",
    "ProviderResult",
    "SafeHttpClient",
    "SourceQuery",
    "SourceType",
    "TopicPolicy",
    "TopicPolicyRegistry",
    "VerificationStatus",
    "is_domain_allowed",
    "sanitize_url",
]

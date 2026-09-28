"""official_sources.ports

공식 출처 수집기 및 HTTP 트랜스포트 인터페이스(Protocol) 정의.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol
from official_sources.models import ProviderResult, SourceQuery, TopicPolicy


class OfficialSourceProvider(Protocol):
    """공식 1차 자료 제공자 포트 인터페이스"""
    provider_id: str

    def supports(self, policy: TopicPolicy) -> bool:
        """해당 정책을 지원하는 제공자인지 판정"""
        ...

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        """질의와 정책에 따라 후보 자료 수집"""
        ...


class HttpTransport(Protocol):
    """테스트 시 mock 주입이 가능한 HTTP 전송 인터페이스"""
    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ) -> Any:
        ...

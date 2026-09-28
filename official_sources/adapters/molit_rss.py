"""official_sources.adapters.molit_rss

국토교통부 공식 RSS 및 보도자료 수집 어댑터:
- RSS는 discovery 용도로 활용하며 실제 보도/공고 상세 URL을 canonical evidence로 유지
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from official_sources.models import (
    OfficialSource,
    ProviderResult,
    SourceQuery,
    SourceType,
    TopicPolicy,
    VerificationStatus,
)
from official_sources.ports import HttpTransport


class MolitRssProvider:
    """국토교통부 공식 RSS 어댑터"""
    provider_id: str = "molit_official_rss"

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self.transport = transport

    def supports(self, policy: TopicPolicy) -> bool:
        return "molit.go.kr" in policy.allowed_domains

    def collect(self, query: SourceQuery, policy: TopicPolicy) -> ProviderResult:
        if not self.supports(policy):
            return ProviderResult(
                provider_id=self.provider_id,
                queries=(f"topic={query.topic_id}",),
                candidates=(),
                rejection_counts={"unsupported_policy": 1},
            )

        candidates: list[OfficialSource] = []
        now = datetime.now(timezone.utc)

        if self.transport is not None:
            try:
                xml_text = self.transport.get("https://www.molit.go.kr/USR/p_etc_rsssvc/m_123/ers.jsp")
                if isinstance(xml_text, str) and "<rss" in xml_text:
                    root = ET.fromstring(xml_text)
                    for item_node in root.findall("./channel/item"):
                        title = item_node.findtext("title", "").strip()
                        link = item_node.findtext("link", "").strip()
                        desc = item_node.findtext("description", "").strip()
                        pub_date_str = item_node.findtext("pubDate", "")

                        if not title or not link:
                            continue

                        published_at = now
                        if pub_date_str:
                            try:
                                # 기본 파싱 또는 fallback
                                published_at = datetime.fromisoformat(pub_date_str)
                                if published_at.tzinfo is None:
                                    published_at = published_at.replace(tzinfo=timezone.utc)
                            except Exception:
                                published_at = now

                        excerpt = desc if len(desc) >= 10 else f"[국토교통부 보도자료] {title} - 상세 정책 발표 원문"
                        content_hash = hashlib.sha256(f"{title}|{excerpt}|{link}".encode("utf-8")).hexdigest()

                        candidates.append(
                            OfficialSource(
                                source_id=f"molit_{hashlib.sha256(link.encode('utf-8')).hexdigest()[:12]}",
                                title=f"국토교통부: {title}",
                                publisher="국토교통부",
                                published_at=published_at,
                                effective_at=published_at,
                                retrieved_at=now,
                                url=link,
                                canonical_url=link,
                                source_type=SourceType.POLICY,
                                evidence_excerpt=excerpt,
                                content_hash=content_hash,
                                verification_status=VerificationStatus.DISCOVERED,
                                final_domain="molit.go.kr",
                                topic_id=policy.topic_id,
                                metadata={"origin_feed": "molit_ers"},
                            )
                        )
            except Exception:
                pass

        return ProviderResult(
            provider_id=self.provider_id,
            queries=(f"molit:topic={query.topic_id}",),
            candidates=tuple(candidates),
            rejection_counts={},
        )

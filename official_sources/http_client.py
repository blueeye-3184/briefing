"""official_sources.http_client

안전한 HTTP 클라이언트 구현체:
- Secret 마스킹 (apiKey, serviceKey 등)
- 429 Retry-After 및 일시적 5xx 재시도 (영구 4xx 미재시도)
- HTTPS 및 도메인 allowlist 검증
- Timeout 기본값 (5, 20) 적용
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import requests

DEFAULT_TIMEOUT = (5.0, 20.0)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 410}

SECRET_PARAM_PATTERN = re.compile(
    r"(?i)(api_?key|service_?key|auth_?key|key|token|secret|password)"
)


def sanitize_url(url: str) -> str:
    """URL의 쿼리 스트링 내 API Key 및 민감 인자 마스킹"""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    sanitized_pairs = []
    for k, v in pairs:
        if SECRET_PARAM_PATTERN.search(k):
            sanitized_pairs.append((k, "[REDACTED]"))
        else:
            sanitized_pairs.append((k, v))
    new_query = urlencode(sanitized_pairs)
    return urlunparse(parsed._replace(query=new_query))


def is_domain_allowed(domain: str, allowed_domains: Sequence[str]) -> bool:
    """도메인 allowlist 검사 (suffix 공격 방지 포함: exact match 또는 .subdomain)"""
    cleaned_domain = domain.lower().split(":")[0]
    for allowed in allowed_domains:
        allowed_clean = allowed.lower().split(":")[0]
        if cleaned_domain == allowed_clean or cleaned_domain.endswith(f".{allowed_clean}"):
            return True
    return False


class SafeHttpClient:
    """공식 출처 수집 전용 안전 HTTP 클라이언트"""

    def __init__(
        self,
        allowed_domains: Sequence[str] = (),
        max_retries: int = 3,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.allowed_domains = tuple(allowed_domains)
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = session or requests.Session()
        self.sleeper = sleeper

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: tuple[float, float] | None = None,
    ) -> requests.Response:
        """GET 요청 실행 (안전 검증 및 재시도)"""
        req_timeout = timeout or self.timeout

        # 1. 초기 URL 도메인 및 HTTPS 검사
        parsed_url = urlparse(url)
        if parsed_url.scheme.lower() != "https":
            raise PermissionError(f"HTTP 요청 거부: HTTPS 프로토콜만 허용됩니다 ({sanitize_url(url)})")
        if self.allowed_domains and not is_domain_allowed(parsed_url.netloc, self.allowed_domains):
            raise PermissionError(
                f"허용되지 않은 도메인: {parsed_url.netloc} ({sanitize_url(url)})"
            )

        attempt = 0
        while True:
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=req_timeout,
                    allow_redirects=True,
                )

                # 2. Redirect 최종 URL 검증
                final_parsed = urlparse(resp.url)
                if final_parsed.scheme.lower() != "https":
                    raise PermissionError("Redirect 대상이 HTTPS가 아닙니다.")
                if self.allowed_domains and not is_domain_allowed(
                    final_parsed.netloc, self.allowed_domains
                ):
                    raise PermissionError(f"Redirect 대상 도메인 불허: {final_parsed.netloc}")

                # 3. 로그인/CAPTCHA 우회 탐지
                resp_text_lower = resp.text[:1000].lower() if resp.text else ""
                if "captcha" in resp_text_lower or "로그인이 필요" in (resp.text or "") or "login" in resp_text_lower:
                    raise PermissionError("공식 출처가 로그인 또는 CAPTCHA를 요구하여 접근이 차단되었습니다.")

                # 4. 상태 코드 분기
                if resp.status_code in NON_RETRYABLE_STATUS_CODES:
                    resp.raise_for_status()

                if resp.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    attempt += 1
                    retry_after = resp.headers.get("Retry-After")
                    delay = 1.0 * (2 ** (attempt - 1))
                    if retry_after:
                        try:
                            delay = min(float(retry_after), 30.0)
                        except ValueError:
                            pass
                    self.sleeper(delay)
                    continue

                resp.raise_for_status()
                return resp

            except requests.exceptions.RequestException as e:
                # 민감정보 살균 예외 발생
                clean_msg = sanitize_url(str(e))
                if attempt < self.max_retries and isinstance(
                    e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
                ):
                    attempt += 1
                    self.sleeper(1.0 * (2 ** (attempt - 1)))
                    continue
                raise type(e)(clean_msg) from None

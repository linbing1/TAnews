import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.PoolTimeout,
)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 1.0  # seconds
_MAX_RETRY_DELAY = 8.0  # seconds


@dataclass
class LLMClient:
    base_url: str
    api_key: str
    model: str

    def _post_chat_once(self, system: str, user: str, *, timeout: float) -> httpx.Response:
        return httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, _RETRYABLE):
            return True
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        return False

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return min(_BASE_RETRY_DELAY * (2 ** (attempt - 1)), _MAX_RETRY_DELAY)

    def complete(
        self,
        system: str,
        user: str,
        *,
        operation: str = "llm.complete",
        timeout: float = 300,
        max_retries: int = _MAX_RETRIES,
    ) -> str:
        for attempt in range(1, max_retries + 1):
            try:
                resp = self._post_chat_once(system, user, timeout=timeout)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except _RETRYABLE as e:
                if attempt == max_retries:
                    raise
                delay = self._retry_delay(attempt)
                logger.warning(
                    "LLM request failed for %s (attempt %d/%d, model=%s, status=-): %s. "
                    "Retrying in %.1fs...",
                    operation,
                    attempt,
                    max_retries,
                    self.model,
                    e,
                    delay,
                )
                time.sleep(delay)
            except httpx.HTTPStatusError as e:
                if not self._should_retry(e) or attempt == max_retries:
                    raise
                response = e.response
                delay = self._retry_delay(attempt, response)
                status = response.status_code if response is not None else "-"
                logger.warning(
                    "LLM request failed for %s (attempt %d/%d, model=%s, status=%s): %s. "
                    "Retrying in %.1fs...",
                    operation,
                    attempt,
                    max_retries,
                    self.model,
                    status,
                    e,
                    delay,
                )
                time.sleep(delay)

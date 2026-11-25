"""Cliente HTTP resiliente para as APIs públicas da Steam.

Resiliência implementada:
* ``requests.Session`` com timeout em toda chamada;
* exponential backoff com jitter: ``min(base * 2**tentativa, teto) + U(0, 1)``;
* retentativa para HTTP 429, 5xx, timeout e erro de conexão;
* respeito ao cabeçalho ``Retry-After`` quando a API envia;
* pausa de polidez entre páginas;
* paginação por cursor com três condições de parada (lista vazia, cursor
  nulo e cursor repetido).
"""
from __future__ import annotations

import json
import logging
import random
import time
from typing import Iterator

import requests

log = logging.getLogger(__name__)

REVIEWS_URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"

RETRY_STATUS = {429, 500, 502, 503, 504}

# Enums da API (documentação IUserReviewsService)
FILTER_RECENT = 1
PURCHASE_TYPE_ALL = 1
REVIEW_TYPE_ALL = 0


class SteamAPIError(RuntimeError):
    """Falha definitiva após esgotar as retentativas."""


class SimulatedRateLimit(requests.HTTPError):
    """HTTP 429 simulado, para demonstrar o backoff no vídeo."""


class SteamClient:
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        polite_pause: float = 1.0,
        simulate_429_rate: float = 0.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.polite_pause = polite_pause
        self.simulate_429_rate = simulate_429_rate
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "fucape-t2-steam-reviews/1.0 (projeto academico)"}
        )
        self.retry_count = 0

    # ------------------------------------------------------------- backoff
    def backoff_delay(self, attempt: int, retry_after: str | None = None) -> float:
        """Tempo de espera antes da próxima tentativa (em segundos)."""
        if retry_after:
            try:
                return min(float(retry_after), self.max_delay)
            except ValueError:
                pass
        return min(self.base_delay * 2 ** attempt, self.max_delay) + random.uniform(0, 1)

    def _get_json(self, url: str, params: dict) -> dict:
        last_error: str = ""
        for attempt in range(self.max_retries + 1):
            retry_after = None
            try:
                if self.simulate_429_rate and random.random() < self.simulate_429_rate:
                    raise SimulatedRateLimit("429 simulado (STEAM_SIMULATE_429_RATE)")
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code in RETRY_STATUS:
                    retry_after = resp.headers.get("Retry-After")
                    last_error = f"HTTP {resp.status_code}"
                else:
                    resp.raise_for_status()
                    return resp.json()
            except SimulatedRateLimit as exc:
                last_error = f"HTTP 429 ({exc})"
            except requests.Timeout:
                last_error = "timeout"
            except requests.ConnectionError as exc:
                last_error = f"erro de conexão: {exc.__class__.__name__}"
            except (requests.HTTPError, json.JSONDecodeError) as exc:
                # 4xx (exceto 429) e JSON inválido não melhoram com retry.
                raise SteamAPIError(f"Falha não recuperável em {url}: {exc}") from exc

            if attempt == self.max_retries:
                break
            delay = self.backoff_delay(attempt, retry_after)
            self.retry_count += 1
            log.warning(
                "[RETRY %d/%d] %s -> %s. Aguardando %.2fs (backoff exponencial + jitter%s).",
                attempt + 1, self.max_retries, url, last_error, delay,
                ", Retry-After" if retry_after else "",
            )
            time.sleep(delay)
        raise SteamAPIError(
            f"Esgotadas {self.max_retries} retentativas em {url}: {last_error}"
        )

    # ------------------------------------------------------------- reviews
    def iter_review_pages(
        self,
        app_id: int,
        language: str = "brazilian",
        max_pages: int = 20,
        num_per_page: int = 100,
    ) -> Iterator[dict]:
        """Itera as páginas de reviews de um app, seguindo o cursor."""
        cursor = "*"
        seen_cursors = set()
        for page in range(1, max_pages + 1):
            payload = {
                "appid": app_id,
                "cursor": cursor,
                "num_per_page": num_per_page,
                "languages": [language],
                "filter": FILTER_RECENT,
                "review_type": REVIEW_TYPE_ALL,
                "purchase_type": PURCHASE_TYPE_ALL,
            }
            data = self._get_json(
                REVIEWS_URL, {"input_json": json.dumps(payload)}
            ).get("response", {})
            reviews = data.get("reviews") or []
            next_cursor = data.get("cursor")
            log.info(
                "app_id=%s página=%d reviews=%d cursor=%s",
                app_id, page, len(reviews), next_cursor,
            )
            if not reviews:
                log.info("app_id=%s: lista vazia, fim da paginação.", app_id)
                return
            data["_page"] = page
            yield data
            seen_cursors.add(cursor)
            if not next_cursor or next_cursor in seen_cursors:
                log.info("app_id=%s: cursor nulo/repetido, fim da paginação.", app_id)
                return
            cursor = next_cursor
            time.sleep(self.polite_pause)

    # ---------------------------------------------------------- appdetails
    def get_app_details(self, app_id: int, lang: str = "brazilian") -> dict | None:
        data = self._get_json(APPDETAILS_URL, {"appids": app_id, "l": lang})
        entry = data.get(str(app_id)) or {}
        if not entry.get("success"):
            log.warning("appdetails sem sucesso para app_id=%s", app_id)
            return None
        return entry.get("data")

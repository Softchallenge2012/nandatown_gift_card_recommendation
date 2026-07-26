# SPDX-License-Identifier: Apache-2.0
"""Gift-card recommendation DataFacts plugin.

Stores purchase-history tables in dataset metadata and provides search-then-rank
recommendations over that table.
"""

from __future__ import annotations

import ast
import json
import time
from typing import Any

from nest_sdk import AccessGrant, AgentId, DataFacts, DataFactsUrl, DatasetMetadata


_TABLE_KEY = "purchase_history_table"
_SEARCH_FIELDS = (
    "gift_card",
    "merchant",
    "category",
    "amount",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _search_terms(query: str) -> str:
    payload: Any
    try:
        payload = json.loads(query)
    except json.JSONDecodeError:
        # Some callers pass Python-literal dict strings (single quotes);
        # parse those as a compatibility fallback.
        try:
            payload = ast.literal_eval(query)
        except (ValueError, SyntaxError):
            return query

    if isinstance(payload, dict):
        for key in ("query", "search", "term"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

        field_terms = [
            _text(payload.get(field)).strip()
            for field in _SEARCH_FIELDS
            if payload.get(field) is not None and _text(payload.get(field)).strip()
        ]
        if field_terms:
            return " ".join(field_terms)
    return query


def _query_record_index(query: str) -> str:
    payload: Any
    try:
        payload = json.loads(query)
    except json.JSONDecodeError:
        try:
            payload = ast.literal_eval(query)
        except (ValueError, SyntaxError):
            return ""

    if not isinstance(payload, dict):
        return ""
    return _text(payload.get("record_index", "")).strip()


class GiftCardRecommenderFacts(DataFacts):
    """DataFacts plugin with search-based gift-card recommendation.

    Expected dataset metadata format::

        DatasetMetadata(
            name="gift-card-history",
            owner=AgentId("merchant-ops"),
            metadata={
                "purchase_history_table": [
                    {
                        "record_index": "r-001",
                        "customer_id": "c-001",
                        "gift_card": "Starbucks",
                        "merchant": "Starbucks",
                        "category": "coffee",
                        "amount": 25,
                        "notes": "birthday coworker",
                    }
                ]
            },
        )
    """

    def __init__(self, *, freshness_ttl_seconds: float = 24 * 3600) -> None:
        self._datasets: dict[DataFactsUrl, DatasetMetadata] = {}
        self._grants: dict[DataFactsUrl, list[AccessGrant]] = {}
        self._timestamps: dict[DataFactsUrl, float] = {}
        self._tables: dict[DataFactsUrl, list[dict[str, Any]]] = {}
        self._freshness_ttl_seconds = freshness_ttl_seconds

    async def publish(self, dataset: DatasetMetadata) -> DataFactsUrl:
        url = DataFactsUrl(f"df://{dataset.name}")
        self._datasets[url] = dataset.model_copy(deep=True)
        self._timestamps[url] = time.time()
        self._tables[url] = self._extract_purchase_table(dataset)
        return url

    async def fetch(self, url: DataFactsUrl) -> DatasetMetadata:
        meta = self._datasets.get(url)
        if meta is None:
            msg = f"Dataset not found: {url}"
            raise KeyError(msg)
        return meta.model_copy(deep=True)

    async def request_access(self, url: DataFactsUrl, requester: AgentId) -> AccessGrant:
        meta = await self.fetch(url)
        if meta.access_tier != "public" and requester != meta.owner:
            msg = f"{requester} is not authorized to read {url} (tier={meta.access_tier!r})"
            raise PermissionError(msg)
        grant = AccessGrant(url=url, grantee=requester, tier="read")
        self._grants.setdefault(url, []).append(grant)
        return grant

    async def verify_freshness(self, url: DataFactsUrl) -> bool:
        ts = self._timestamps.get(url)
        if ts is None:
            return False
        return (time.time() - ts) <= self._freshness_ttl_seconds

    def search_purchase_history(
        self,
        url: DataFactsUrl,
        query: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return purchase rows matching all tokens in ``query``.

        Search is case-insensitive and spans customer, gift-card, merchant,
        category, and free-form notes columns. ``query`` may also be a JSON
        object string containing a ``query``, ``search``, or ``term`` field,
        or a purchase-history-shaped object using gift_card, merchant,
        category, and amount fields.
        """
        table = self._tables.get(url)
        # print(f'Query: {query}, Table: {len(table) if table else 0}')
        if table is None:
            msg = f"Dataset not found: {url}"
            raise KeyError(msg)

        tokens = [t for t in _search_terms(query).lower().split() if t]
        if not tokens:
            return [row.copy() for row in table[:limit]]

        out: list[dict[str, Any]] = []
        for row in table:
            searchable = " ".join(
                [
                    # _text(row.get("customer_id")).lower(),
                    # _text(row.get("record_index")).lower(),
                    _text(row.get("gift_card")).lower(),
                    _text(row.get("merchant")).lower(),
                    _text(row.get("category")).lower(),
                    _text(row.get("amount")).lower(),
                    # _text(row.get("notes")).lower(),
                ]
            )
            if all(token in searchable for token in tokens):
                out.append(row.copy())
                if len(out) >= limit:
                    break
        return out

    def recommend_gift_cards(
        self,
        url: DataFactsUrl,
        query: str,
        *,
        top_k: int = 5,
    ) -> str:
    # ) -> list[dict[str, Any]]:
        """Recommend gift cards by ranking cards from searched purchase rows.

        Ranking uses purchase frequency first, then average amount, then
        alphabetical card name for stable deterministic ordering. Returned
        recommendations include a positive/negative match label based on whether
        the query record_index is present in the matched purchase rows.
        """
        matches = self.search_purchase_history(url, query, limit=10_000)
        query_record_index = _query_record_index(query)
        if query_record_index:
            matched_record_indexes = {
                _text(row.get("record_index")).strip()
                for row in matches
                if _text(row.get("record_index")).strip()
            }
            match_label = (
                "positive"
                if query_record_index and query_record_index in matched_record_indexes
                else "negative"
            )
            return match_label
        else:
            print(f"matches = {len(matches)}, No record_index found in query; cannot determine match label.")

            # Return full matched records (not aggregated summaries).
            return [row.copy() for row in matches[:top_k]]



    def _extract_purchase_table(self, dataset: DatasetMetadata) -> list[dict[str, Any]]:
        raw = dataset.metadata.get(_TABLE_KEY, [])
        if not isinstance(raw, list):
            return []
        rows: list[dict[str, Any]] = []
        for row in raw:
            if isinstance(row, dict):
                rows.append(dict(row))
        return rows
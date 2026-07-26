#!/usr/bin/env python3
"""Print trust scores for a list of agents.

Usage:
    uv run python scripts/print_trust_scores.py
"""

from __future__ import annotations


from pathlib import Path
import asyncio
import ast
import csv
import json
import math
import pickle
from typing import Iterable
import pandas as pd

from nest_core.layers.trust import Trust
from nest_core.types import AgentId, Evidence
from nest_sdk import DatasetMetadata

from nest_plugins_reference.datafacts.gift_card_recommender import GiftCardRecommenderFacts
from nest_plugins_reference.trust.score_average import ScoreAverageTrust
import time

SELLER_COUNT = 100
BUYER_COUNT = 10


def clean_categories(text: str) -> str:
    if not text:
        return ""
    arr = ast.literal_eval(text)
    return arr[-1] if arr else ""


class GiftCardPolicyCompat:
    """Compatibility class for unpickling models saved from preprocessing.py."""

    def _ensure_prompt(self, prompt: str) -> None:
        if prompt not in self.logits:
            self.logits[prompt] = [0.0] * self.num_actions

    def _softmax(self, logits: list[float]) -> list[float]:
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        total = sum(exps)
        return [e / total for e in exps]


class _PolicyUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if module == "__main__" and name == "GiftCardPolicy":
            return GiftCardPolicyCompat
        return super().find_class(module, name)


_POLICY: GiftCardPolicyCompat | None = None


def _load_policy() -> GiftCardPolicyCompat:
    global _POLICY
    if _POLICY is not None:
        return _POLICY

    policy_path = Path("models/gift_card_policy.pk")
    with policy_path.open("rb") as fp:
        _POLICY = _PolicyUnpickler(fp).load()
    return _POLICY


async def print_trust_scores(trust: Trust, agents: Iterable[AgentId]) -> None:
    """Print score, confidence, and sample count for each agent."""
    print("agent_id\tscore\tconfidence\tsamples")
    for agent in agents:
        rep = await trust.score(agent)
        print(f"{rep.agent_id}\t{rep.score:.3f}\t{rep.confidence:.3f}\t{rep.sample_count}")


def _seller_agent(index: int) -> AgentId:
    return AgentId(f"seller-{index:03d}")


def _buyer_agent(index: int) -> AgentId:
    return AgentId(f"buyer-{index:03d}")


def _seller_purchase_history(index: int) -> list[dict[str, object]]:
    # category = CATEGORIES[index % len(CATEGORIES)]
    # merchant = f"merchant-{index:03d}"
    # gift_card = f"GiftCard-{index:03d}"
    # amount = 25 + (index % 5) * 10
    # rows: list[dict[str, object]] = []

    # for offset in range(3):
    #     rows.append(
    #         {
    #             "record_index": f"seller-{index:03d}-record-{offset:02d}",
    #             "customer_id": f"customer-{index:03d}-{offset:02d}",
    #             "gift_card": gift_card,
    #             "merchant": merchant,
    #             "category": category,
    #             "amount": amount + offset * 5,
    #             "notes": f"{category} purchase {offset}",
    #         }
    #     )
    csv_path = Path("data/test_gift.csv")
    if not csv_path.exists():
        csv_path = Path("data/gift_card/test_gift.csv")

    policy = _load_policy()

    purchase_history_table = []
    # with csv_path.open("r", encoding="utf-8", newline="") as fp:
    #     reader = csv.DictReader(fp)
    df = pd.read_csv(csv_path)
    df = df.fillna(0)
    df = df.iloc[:1000]
    for i, row in df.iterrows():
        amount_raw = row.get("amount", 0)
        title = row.get("gift_card", "")
        if title == "":
            pred_label = ""
        else:
            policy._ensure_prompt(title)
            probs = policy._softmax(policy.logits[title])
            pred_idx = max(range(len(probs)), key=lambda i: probs[i])
            pred_label = policy.actions[pred_idx]
        
        category = clean_categories(row.get("category", ""))

        purchase_history_table.append(
            {
                "record_index": str(i),
                "customer_id": row.get("customer_id", ""),
                "gift_card": pred_label,
                "merchant": row.get("merchant", ""),
                "category": category,
                "amount": float(amount_raw),
                "notes": row.get("notes", ""),
            }
        )
    return purchase_history_table


def _buyer_query(buyer_index: int) -> str:
    # category = CATEGORIES[seller_index % len(CATEGORIES)]
    # merchant = f"merchant-{seller_index:03d}"
    # gift_card = f"GiftCard-{seller_index:03d}"
    # amount = 25 + (seller_index % 5) * 10
    # # is_positive = (seller_index + buyer_index) % 2 == 0
    # # if is_positive:
    # #     record_index = f"seller-{seller_index:03d}-record-00"
    # # else:
    # #     record_index = f"buyer-{buyer_index:03d}-mismatch-{seller_index:03d}"
    
    record_index = str(buyer_index)
    csv_path = Path("data/gift_card/test_gift.csv")
    df = pd.read_csv(csv_path)
    df = df.fillna(0)
    
    row = df.iloc[buyer_index]

    amount_raw = (row.get("amount") or "")
    policy = _load_policy()

    title = row.get("gift_card", "")
    if title == "":
        pred_label = ""
    else:
        policy._ensure_prompt(title)
        probs = policy._softmax(policy.logits[title])
        pred_idx = max(range(len(probs)), key=lambda i: probs[i])
        pred_label = policy.actions[pred_idx]
    
    category = clean_categories(row.get("category", ""))
        
    return json.dumps(
        {
            "record_index": record_index,
            "gift_card": pred_label,
            "merchant": row.get("merchant", "").strip(),
            "category": category,
            "amount": amount_raw,
        }
    )


async def run_recommendation_record(query: dict[str, object]) -> dict[str, object] | None:
    """Run one recommendation query and return a single full record when available."""
    facts = GiftCardRecommenderFacts()
    index = 0
    seller = _seller_agent(index)
    buyer = _buyer_agent(index)
    published_urls = {}

    dataset = DatasetMetadata(
        name=f"gift-card-history-{index:03d}",
        owner=seller,
        metadata={"purchase_history_table": _seller_purchase_history(index)},
    )
    published_urls[seller] = await facts.publish(dataset)


    policy = _load_policy()
    row = query
    title = row.get("gift_card", "")
    if title == "":
        pred_label = ""
    else:
        policy._ensure_prompt(title)
        probs = policy._softmax(policy.logits[title])
        pred_idx = max(range(len(probs)), key=lambda i: probs[i])
        pred_label = policy.actions[pred_idx]
    
    category = clean_categories(row.get("category", ""))

    query['gift_card'] = pred_label
    query['category'] = category
    query_str = json.dumps(query)
    print(f"query_str={query_str}")
    record_rank = facts.recommend_gift_cards(published_urls[seller], query_str)

    if isinstance(record_rank, list):
        if not record_rank:
            return None
        first = record_rank[0]
        if isinstance(first, dict):
            return dict(first)
        return {"result": first}

    if isinstance(record_rank, dict):
        return dict(record_rank)

    return {"result": record_rank}


async def run_recommendation_marketplace(trust: Trust) -> tuple[list[AgentId], list[AgentId]]:
    """Simulate buyers evaluating seller recommendations and reporting trust evidence."""
    facts = GiftCardRecommenderFacts()
    sellers = [_seller_agent(index) for index in range(SELLER_COUNT)]
    buyers = [_buyer_agent(index) for index in range(BUYER_COUNT)]
    published_urls = {}

    for index, seller in enumerate(sellers):
        dataset = DatasetMetadata(
            name=f"gift-card-history-{index:03d}",
            owner=seller,
            metadata={"purchase_history_table": _seller_purchase_history(index)},
        )
        published_urls[seller] = await facts.publish(dataset)

    for buyer_index, buyer in enumerate(buyers):
        for seller_index, seller in enumerate(sellers):
            query = _buyer_query(buyer_index)
            verdict = facts.recommend_gift_cards(published_urls[seller], query)
            # print(f"query={query}")
            # print(f"verdict={verdict}")
            await trust.report(
                seller,
                Evidence(
                    reporter=buyer,
                    subject=seller,
                    kind=verdict,
                    detail=f"recommendation query against {seller}",
                ),
            )
            await trust.report(
                buyer,
                Evidence(
                    reporter=seller,
                    subject=buyer,
                    kind=verdict,
                    detail=f"buyer evaluation for {seller}",
                ),
            )
    # print(_seller_purchase_history(0))
    return sellers, buyers


async def main() -> None:
    # trust = ScoreAverageTrust()
    # sellers, buyers = await run_recommendation_marketplace(trust)
    
    # print("sellers")
    # await print_trust_scores(trust, sellers)
    # print()
    # print("buyers")
    # await print_trust_scores(trust, buyers)
    query = {'gift_card':'Amazon.com Gift Card for any amount in various designs',
    'merchant':'Amazon',
    'category':"['Gift Cards', 'Amazon Incentives Brand Guidelines']",
    'amount':'15.0'}
    record_rank = await run_recommendation_record(query)
    print(f"record_rank={record_rank}")
    return record_rank


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    print(f"Execution time: {time.time() - start:.2f} seconds")

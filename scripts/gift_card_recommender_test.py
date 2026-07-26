# SPDX-License-Identifier: Apache-2.0
"""Tests for gift-card recommendation DataFacts plugin."""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

from nest_sdk import AgentId, DatasetMetadata
from preprocessing import *
from nest_plugins_reference.datafacts.gift_card_recommender import GiftCardRecommenderFacts


async def main():

    facts = GiftCardRecommenderFacts()
    csv_path = Path("data/test_gift.csv")
    if not csv_path.exists():
        csv_path = Path("data/gift_card/test_gift.csv")
    
    policy_path = Path("./models/gift_card_policy.pk")
    
    with policy_path.open("rb") as f:
        policy = pickle.load(f)

    purchase_history_table = []
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for i, row in enumerate(reader, start=1):
            amount_raw = (row.get("amount") or "").strip()
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
                    "record_index": f"r-{i:03d}",
                    "customer_id": row.get("customer_id", ""),
                    "gift_card": pred_label,
                    "merchant": row.get("merchant", ""),
                    "category": category,
                    "amount": float(amount_raw) if amount_raw else "",
                    "notes": row.get("notes", ""),
                }
            )
    
    for v in purchase_history_table:
        title = v['gift_card']
        policy._ensure_prompt(title)
        probs = policy._softmax(policy.logits[title])
        pred_idx = max(range(len(probs)), key=lambda i: probs[i])
        pred_label = policy.actions[pred_idx]
        

    dataset = DatasetMetadata(
        name="gift-card-history",
        owner=AgentId("merchant-ops"),
        metadata={
            "purchase_history_table": purchase_history_table
        },
    )

    url = await facts.publish(dataset)
    fetched = await facts.fetch(url)
    print(fetched.name)# "gift-card-history"

    coffee_rows = purchase_history_table[:1]
    print(len(coffee_rows)) # 1
    print([row["gift_card"] for row in coffee_rows])


# PYTHONPATH=packages/nest-core:packages/nest-sdk:packages/nest-plugins-reference python gift_card_recommender_test.py
if __name__ == "__main__":
    asyncio.run(main())


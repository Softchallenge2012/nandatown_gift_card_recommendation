#!/usr/bin/env python3
"""Flask demo for the gift card lookup website.

Run with:
  PYTHONPATH=packages/nest-plugins-reference:packages/nest-core:packages/nest-sdk:scripts \
  python scripts/gift_card_flask_demo.py
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from flask import Flask, render_template_string, request
from print_trust_scores import run_recommendation_record


def _prepare_query(form_data: dict[str, str]) -> dict[str, Any]:
  category_raw = form_data.get("category", "").strip()
  if category_raw and not category_raw.startswith("["):
    # print_trust_scores.clean_categories expects a Python-list string.
    category_for_model = str(["Gift Cards", category_raw])
  else:
    category_for_model = category_raw

  amount_raw = form_data.get("amount", "").strip()
  amount_value: Any = amount_raw
  if amount_raw:
    try:
      amount_value = float(amount_raw)
    except ValueError:
      amount_value = amount_raw

  return {
    "gift_card": form_data.get("gift_card", "").strip(),
    "merchant": form_data.get("merchant", "").strip(),
    "category": category_for_model,
    "amount": amount_value,
  }


async def _lookup_record(form_data: dict[str, str]) -> tuple[dict[str, Any] | None, float]:
  start = time.perf_counter()
  query = _prepare_query(form_data)
  print(f"Prepared query: {query}")

  result =  await run_recommendation_record(query)
  print(f"run_recommendation_record returned: {result}")

  if result is None:
    record = None
  elif isinstance(result, dict):
    record = dict(result)
  elif isinstance(result, list) and result and isinstance(result[0], dict):
    record = dict(result[0])
  else:
    record = {"result": result}

  elapsed = time.perf_counter() - start
  return record, elapsed


app = Flask(__name__)


PAGE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Gift Card Lookup Demo</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f0e8;
        --panel: #fffaf3;
        --ink: #181513;
        --muted: #6c5f54;
        --accent: #a04d28;
        --accent-soft: rgba(160, 77, 40, 0.12);
        --line: rgba(24, 21, 19, 0.14);
        --shadow: 0 24px 80px rgba(24, 21, 19, 0.12);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(160, 77, 40, 0.18), transparent 32%),
          radial-gradient(circle at top right, rgba(120, 141, 116, 0.16), transparent 28%),
          linear-gradient(180deg, #f8f4ee 0%, var(--bg) 100%);
        min-height: 100vh;
      }

      .shell {
        max-width: 1080px;
        margin: 0 auto;
        padding: 40px 20px 56px;
      }

      .hero {
        display: grid;
        gap: 16px;
        grid-template-columns: 1.2fr 0.8fr;
        align-items: end;
        margin-bottom: 22px;
      }

      .eyebrow {
        margin: 0 0 8px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.72rem;
        color: var(--muted);
      }

      h1 {
        margin: 0;
        font-size: clamp(2.2rem, 4vw, 4rem);
        line-height: 0.95;
        letter-spacing: -0.04em;
      }

      .lede {
        margin: 0;
        max-width: 60ch;
        color: var(--muted);
        font-size: 1.02rem;
        line-height: 1.6;
      }

      .meta {
        justify-self: end;
        display: flex;
        flex-direction: column;
        gap: 12px;
        align-items: flex-end;
        text-align: right;
      }

      .pill {
        border: 1px solid var(--line);
        background: rgba(255, 250, 243, 0.75);
        border-radius: 999px;
        padding: 10px 14px;
        font-size: 0.88rem;
        box-shadow: var(--shadow);
      }

      .grid {
        display: grid;
        grid-template-columns: 1fr 1.1fr;
        gap: 20px;
        align-items: start;
      }

      .card {
        background: rgba(255, 250, 243, 0.92);
        border: 1px solid var(--line);
        border-radius: 28px;
        box-shadow: var(--shadow);
        overflow: hidden;
      }

      .card-header {
        padding: 24px 24px 0;
      }

      .card-body {
        padding: 24px;
      }

      .section-title {
        margin: 0;
        font-size: 1.35rem;
        letter-spacing: -0.02em;
      }

      .section-copy {
        margin: 8px 0 0;
        color: var(--muted);
        line-height: 1.55;
      }

      form {
        display: grid;
        gap: 14px;
      }

      label {
        display: block;
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 8px;
      }

      input {
        width: 100%;
        border: 1px solid rgba(24, 21, 19, 0.14);
        background: #fffdf9;
        border-radius: 18px;
        padding: 14px 16px;
        font-size: 1rem;
        color: var(--ink);
        outline: none;
        transition: border-color 160ms ease, transform 160ms ease;
      }

      input:focus {
        border-color: rgba(160, 77, 40, 0.55);
        transform: translateY(-1px);
      }

      .actions {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 6px;
      }

      button {
        border: 0;
        border-radius: 999px;
        background: var(--ink);
        color: #fff;
        padding: 12px 18px;
        font-size: 0.95rem;
        font-weight: 600;
        cursor: pointer;
      }

      .ghost {
        background: var(--accent-soft);
        color: var(--accent);
      }

      .result-banner {
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 16px 18px;
        background: linear-gradient(135deg, rgba(160, 77, 40, 0.08), rgba(120, 141, 116, 0.08));
        display: grid;
        gap: 6px;
        margin-bottom: 18px;
      }

      .result-banner strong {
        font-size: 1.15rem;
      }

      .time {
        color: var(--muted);
        font-variant-numeric: tabular-nums;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        overflow: hidden;
      }

      th, td {
        text-align: left;
        vertical-align: top;
        padding: 14px 12px;
        border-bottom: 1px solid rgba(24, 21, 19, 0.1);
        font-size: 0.95rem;
      }

      th {
        width: 180px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--muted);
        font-size: 0.72rem;
      }

      .empty {
        margin: 0;
        color: var(--muted);
      }

      @media (max-width: 880px) {
        .hero,
        .grid {
          grid-template-columns: 1fr;
        }

        .meta {
          justify-self: start;
          align-items: flex-start;
          text-align: left;
        }

        th {
          width: 120px;
        }
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Flask hosted demo</p>
          <h1>Gift card record lookup</h1>
          <p class="lede">Enter <strong>gift_card</strong>, <strong>merchant</strong>, <strong>category</strong>, and <strong>amount</strong>. The demo sends this input to <code>run_recommendation_record</code> and renders the full returned record.</p>
        </div>
        <div class="meta">
          <div class="pill">Hosted with Flask</div>
          <div class="pill">Backed by run_recommendation_record</div>
        </div>
      </section>

      <section class="grid">
        <article class="card">
          <div class="card-header">
            <p class="eyebrow">Input form</p>
            <h2 class="section-title">Search with model input</h2>
            <p class="section-copy">Use four fields as query input. The server calls run_recommendation_record and returns the full output record.</p>
          </div>
          <div class="card-body">
            <form method="post">
              <div>
                <label for="gift_card">Gift card</label>
                <input id="gift_card" name="gift_card" value="{{ form_values.gift_card }}" placeholder="Amazon.com Gift Card for any amount in various designs" required />
              </div>
              <div>
                <label for="merchant">Merchant</label>
                <input id="merchant" name="merchant" value="{{ form_values.merchant }}" placeholder="Amazon" required />
              </div>
              <div>
                <label for="category">Category</label>
                <input id="category" name="category" value="{{ form_values.category }}" placeholder="['Gift Cards', 'Amazon Incentives Brand Guidelines']" required />
              </div>
              <div>
                <label for="amount">Amount</label>
                <input id="amount" name="amount" value="{{ form_values.amount }}" placeholder="15.0" required />
              </div>
              <div class="actions">
                <button type="submit">Find record</button>
                <button class="ghost" type="button" onclick="window.location.href='/'">Reset</button>
              </div>
            </form>
          </div>
        </article>

        <article class="card">
          <div class="card-header">
            <p class="eyebrow">Result field</p>
            <h2 class="section-title">Recommendation result</h2>
          </div>
          <div class="card-body">
            <div class="result-banner">
              <strong>{{ message }}</strong>
              <div class="time">Total time: {{ elapsed_ms }} ms</div>
            </div>

            {% if record_items %}
              <table>
                <tbody>
                  {% for key, value in record_items %}
                    <tr><th>{{ key }}</th><td>{{ value }}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            {% else %}
              <p class="empty">No result returned. Check the four fields and try again.</p>
            {% endif %}
          </div>
        </article>
      </section>
    </main>
  </body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    record_items: list[tuple[str, Any]] = []
    elapsed_ms = "0.00"
    message = "Enter input and submit to run recommendation lookup."
    form_values = {"gift_card": "", "merchant": "", "category": "", "amount": ""}

    if request.method == "POST":
        form_values = {
            "gift_card": request.form.get("gift_card", ""),
            "merchant": request.form.get("merchant", ""),
            "category": request.form.get("category", ""),
            "amount": request.form.get("amount", ""),
        }
        try:
            record, elapsed = _lookup_record(form_values)
            elapsed_ms = f"{elapsed * 1000:.2f}"
            if record:
                record_items = list(record.items())
                message = "Recommendation lookup succeeded. Showing the full returned record."
            else:
                message = "Recommendation lookup returned no record."
        except Exception as exc:  # pragma: no cover - demo UI error path
            message = f"Recommendation lookup failed: {exc}"

    return render_template_string(
        PAGE,
        record_items=record_items,
        elapsed_ms=elapsed_ms,
        message=message,
        form_values=form_values,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
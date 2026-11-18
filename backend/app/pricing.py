"""Zuna smart-pricing engine (version 1).

Two layers, exactly as described in the project document:

1. A deterministic, explainable calculation engine (this file, pure Python).
   It computes every number: total cost, base price, suggested listing price,
   negotiation floor and profit.
2. An optional AI *explanation* layer (Gemini). It may only reword numbers the
   engine already produced. It can never set or change a price, and its output is
   discarded if it mentions a rupee amount the engine did not calculate.

Formulas
--------
    C  = M + L + P + O                      (material + labour + packaging + other)
    Ps = C / (1 - m/100)                    (price that gives margin m on the selling price)

The engine then applies two small, bounded, explainable adjustments and a negotiation buffer:
    * demand     : -10% (very low demand) .. +10% (very high demand)
    * stock age  : 0% up to 30 days, then 0.1% per day, capped at 15%
    * buffer     : +5% so the seller has room to accept lower offers

Stock age only changes a *recommendation*; the seller always decides the final price
and the minimum they will accept.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

NEGOTIATION_BUFFER = 0.05
DEMAND_SWING = 0.10
MAX_AGE_DISCOUNT = 0.15
AGE_DISCOUNT_STARTS_AFTER_DAYS = 30
AGE_DISCOUNT_PER_DAY = 0.001
CLEARANCE_AGE_DAYS = 60

# Share of the listing margin the seller is still willing to accept when negotiating.
# Older stock => the seller is prepared to give up more margin.
FLOOR_MARGIN_SHARE_FRESH = 0.50   # up to 30 days
FLOOR_MARGIN_SHARE_AGEING = 0.45  # 31-60 days
FLOOR_MARGIN_SHARE_OLD = 0.30     # 60+ days
NO_COST_FLOOR_SHARE = 0.70        # when the seller did not record a cost

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def demand_level(demand_index: int) -> str:
    if demand_index < 34:
        return "low"
    if demand_index < 67:
        return "medium"
    return "high"


DEMAND_LABEL_TO_INDEX = {"low": 20, "medium": 50, "high": 80}


def round_price(value: float) -> int:
    """Round to a shop-friendly price: nearest 10 for larger prices, nearest 5 or 1 for small ones."""
    step = 10 if value >= 200 else 5 if value >= 50 else 1
    return int(round(value / step) * step)


def age_discount(inventory_age_days: int) -> float:
    extra_days = max(0, inventory_age_days - AGE_DISCOUNT_STARTS_AFTER_DAYS)
    return min(MAX_AGE_DISCOUNT, extra_days * AGE_DISCOUNT_PER_DAY)


def demand_adjustment(demand_index: int) -> float:
    return (demand_index - 50) / 50 * DEMAND_SWING


def stock_age_band(inventory_age_days: int) -> dict[str, str]:
    """Stock-age table from the project document. A recommendation, never an automatic price cut."""
    if inventory_age_days <= 15:
        return {"band": "0-15 days", "recommendation": "Normal recommended price."}
    if inventory_age_days <= 30:
        return {"band": "16-30 days", "recommendation": "Monitor demand."}
    if inventory_age_days <= CLEARANCE_AGE_DAYS:
        return {"band": "31-60 days", "recommendation": "Consider a small discount."}
    return {"band": "60+ days", "recommendation": "Consider a clearance offer."}


def _floor_margin_share(inventory_age_days: int) -> float:
    if inventory_age_days <= AGE_DISCOUNT_STARTS_AFTER_DAYS:
        return FLOOR_MARGIN_SHARE_FRESH
    if inventory_age_days <= CLEARANCE_AGE_DAYS:
        return FLOOR_MARGIN_SHARE_AGEING
    return FLOOR_MARGIN_SHARE_OLD


def negotiation_floor(total_cost: float, margin_percent: float, inventory_age_days: int) -> int:
    """Lowest price the engine suggests the seller accepts: keeps part of the margin, never below cost."""
    floor_margin = (margin_percent / 100) * _floor_margin_share(inventory_age_days)
    return round_price(total_cost / (1 - floor_margin))


def default_negotiation_floor(price: int, cost: int, inventory_age_days: int = 0) -> int:
    """Automatic minimum acceptable price for a listing whose seller has not set one.

    Uses the listing's own margin. Always between cost (when known) and the listing price.
    """
    if price <= 0:
        return 0
    if cost <= 0:
        floor = round_price(price * NO_COST_FLOOR_SHARE)
    elif cost >= price:
        floor = price
    else:
        listing_margin = (price - cost) / price
        floor_margin = listing_margin * _floor_margin_share(inventory_age_days)
        floor = round_price(cost / (1 - floor_margin))
    return max(min(floor, price), min(cost, price))


def calculate_price(
    *,
    total_cost: int,
    cost_breakdown: dict[str, int] | None,
    target_margin_percent: float,
    inventory_age_days: int,
    demand_index: int,
    category: str | None = None,
) -> dict[str, Any]:
    margin = target_margin_percent / 100
    base_price = total_cost / (1 - margin)
    age_cut = age_discount(inventory_age_days)
    demand_change = demand_adjustment(demand_index)
    adjusted = base_price * (1 - age_cut) * (1 + demand_change) * (1 + NEGOTIATION_BUFFER)
    suggested = max(total_cost, round_price(adjusted))
    floor = min(suggested, max(total_cost, negotiation_floor(total_cost, target_margin_percent, inventory_age_days)))
    band = stock_age_band(inventory_age_days)
    result: dict[str, Any] = {
        # Fields the existing frontend already renders.
        "unitCost": total_cost,
        "targetMarginPercent": target_margin_percent,
        "inventoryAgeDays": inventory_age_days,
        "demandIndex": demand_index,
        "basePrice": int(round(base_price)),
        "suggestedPrice": suggested,
        "actualMarginPercent": round((suggested - total_cost) / suggested * 100, 1),
        "adjustmentPercent": round(((1 - age_cut) * (1 + demand_change) * (1 + NEGOTIATION_BUFFER) - 1) * 100, 1),
        # Extra detail for the full pricing assistant / API consumers.
        "category": category,
        "totalCost": total_cost,
        "costBreakdown": cost_breakdown,
        "demandLevel": demand_level(demand_index),
        "demandAdjustmentPercent": round(demand_change * 100, 1),
        "stockAgeAdjustmentPercent": round(-age_cut * 100, 1),
        "negotiationBufferPercent": round(NEGOTIATION_BUFFER * 100, 1),
        "stockAge": band,
        "negotiationFloor": floor,
        "estimatedProfit": suggested - total_cost,
        "profitAtFloor": floor - total_cost,
    }
    result["explanation"] = build_explanation(result)
    result["explanationSource"] = "rules"
    return result


def _rupees(value: int) -> str:
    return f"₹{value:,}"


def build_explanation(result: dict[str, Any]) -> str:
    """Plain-language 'Why this price?' text generated directly from the calculation."""
    parts = [
        f"Your total cost is {_rupees(result['totalCost'])}. "
        f"To keep a {result['targetMarginPercent']:g}% margin the base price is {_rupees(result['basePrice'])}.",
        f"Demand looks {result['demandLevel']} ({result['demandAdjustmentPercent']:+g}% adjustment).",
    ]
    if result["stockAgeAdjustmentPercent"]:
        parts.append(
            f"Stock has been listed for {result['inventoryAgeDays']} days, so a {abs(result['stockAgeAdjustmentPercent']):g}% "
            f"age discount is built in. {result['stockAge']['recommendation']}"
        )
    else:
        parts.append(
            f"Stock has been listed for {result['inventoryAgeDays']} days. {result['stockAge']['recommendation']}"
        )
    parts.append(
        f"A {result['negotiationBufferPercent']:g}% negotiation buffer leaves room for offers, giving a suggested listing price "
        f"of {_rupees(result['suggestedPrice'])} (about {_rupees(result['estimatedProfit'])} profit per item)."
    )
    parts.append(
        f"Suggested minimum to accept: {_rupees(result['negotiationFloor'])} "
        f"({_rupees(result['profitAtFloor'])} profit). You always make the final decision."
    )
    parts.append("This is a transparent rules-based estimate, not an AI prediction.")
    return " ".join(parts)


def _allowed_amounts(result: dict[str, Any]) -> set[int]:
    keys = ("totalCost", "basePrice", "suggestedPrice", "negotiationFloor", "estimatedProfit", "profitAtFloor")
    allowed = {int(result[key]) for key in keys}
    allowed.update((result.get("costBreakdown") or {}).values())
    return allowed


def _only_known_amounts(text: str, allowed: set[int]) -> bool:
    for match in re.findall(r"₹\s?([\d,]+)", text):
        digits = match.replace(",", "")
        if digits and int(digits) not in allowed:
            return False
    return True


def gemini_explanation(result: dict[str, Any], timeout: float = 6.0) -> str | None:
    """Ask Gemini to reword the calculation. Returns None when unavailable or unsafe.

    Needs GEMINI_API_KEY (and optionally GEMINI_MODEL). Any failure falls back silently
    to the rules-based explanation, so pricing never depends on the AI service.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    facts = {
        "category": result.get("category"),
        "total_cost": result["totalCost"],
        "target_margin_percent": result["targetMarginPercent"],
        "base_price": result["basePrice"],
        "demand": result["demandLevel"],
        "inventory_age_days": result["inventoryAgeDays"],
        "stock_age_advice": result["stockAge"]["recommendation"],
        "suggested_listing_price": result["suggestedPrice"],
        "suggested_minimum_to_accept": result["negotiationFloor"],
        "estimated_profit_at_listing": result["estimatedProfit"],
    }
    prompt = (
        "You help small Indian artisans understand a price recommendation. Explain in 3-4 short, friendly sentences "
        "why the price below was recommended. Use ONLY the numbers in the JSON, write money as ₹ amounts, never invent "
        "or change a number, never suggest a different price, and remind the seller they decide the final price.\n"
        + json.dumps(facts, ensure_ascii=False)
    )
    request = urllib.request.Request(
        GEMINI_URL.format(model=model),
        data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError):
        return None
    if not text or len(text) > 900 or not _only_known_amounts(text, _allowed_amounts(result)):
        return None
    return text


def with_ai_explanation(result: dict[str, Any]) -> dict[str, Any]:
    """Attach a Gemini-worded explanation if available; numbers are never touched."""
    ai_text = gemini_explanation(result)
    if ai_text:
        result["aiExplanation"] = ai_text
        result["explanation"] = (
            f"{ai_text} The price is calculated by Zuna's rules engine, not an AI prediction; "
            "an AI model only worded this explanation."
        )
        result["explanationSource"] = "gemini"
    return result

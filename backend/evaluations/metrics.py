"""Small deterministic checks; citation entailment still needs human review."""
import re
from urllib.parse import urlsplit

LINK = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)")
# USD / million tokens; official pricing page checked 2026-09-09.
# Report a peak/off-peak interval, not a billed invoice.
RATES = {"deepseek-v4-flash": (0.007, 0.22, 0.66), "deepseek-v4-pro": (0.022, 0.66, 1.98)}
PRICE_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"


def estimate(usage_by_model):
    low = 0.0
    unknown = []
    for model, usage in usage_by_model.items():
        rate = RATES.get(model)
        if rate is None or not {"input_tokens", "output_tokens"} <= usage.keys():
            unknown.append(model)
            continue
        cached = usage.get("input_token_details", {}).get("cache_read")
        if cached is None:
            unknown.append(model + ":cache_usage_missing")
            continue
        input_tokens, output_tokens = usage["input_tokens"], usage["output_tokens"]
        if not 0 <= cached <= input_tokens:
            unknown.append(model + ":invalid_cache_usage")
            continue
        low += (cached * rate[0] + (input_tokens-cached) * rate[1] + output_tokens*rate[2])/1_000_000
    return {"known_model_usd_interval": [round(low, 8), round(low*2, 8)],
            "unknown_models": unknown, "complete_model_usage": bool(usage_by_model) and not unknown,
            "excludes": ["embedding", "web_search_service_fee", "failed_requests_without_usage"],
            "price_source": PRICE_SOURCE, "price_checked": "2026-09-09"}


def citation_checks(text, sources):
    links = sorted(set(LINK.findall(text)))
    observed = {s.get("url") for s in sources}
    return {"links": links, "links_observed_in_tool_evidence": [u for u in links if u in observed],
            "unobserved_links": [u for u in links if u not in observed],
            "domains": sorted({urlsplit(u).hostname for u in links}),
            "entailment": "requires_human_review"}

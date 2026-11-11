"""Price snapshots: a list of reference products quoted in several regions on one date."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .client import HOURS_PER_MONTH, Item, ProductNotFound, Transport, quote
from .specs import DATA_DIR

SNAPSHOT_DIR = DATA_DIR / "snapshots"
SAMPLES_PATH = DATA_DIR / "samples.json"

# Turns a sample and a billing mode into the request line to price.
Resolver = Callable[[dict, str], Item]


def load_samples(path: Path = SAMPLES_PATH) -> List[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["samples"]


def take_snapshot(
    samples: Iterable[dict],
    regions: Iterable[str],
    resolve: Resolver,
    transport: Optional[Transport] = None,
    today: Optional[date] = None,
) -> dict:
    """Quote every sample in every region. A product that is not offered becomes null."""
    samples = list(samples)
    prices: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}
    for region in regions:
        region_prices: Dict[str, Dict[str, Optional[float]]] = {}
        for sample in samples:
            by_billing: Dict[str, Optional[float]] = {}
            for billing in sample["billing"]:
                item = resolve(sample, billing)
                try:
                    by_billing[billing] = quote([item], region, billing, transport=transport).total
                except ProductNotFound:
                    by_billing[billing] = None
            region_prices[sample["id"]] = by_billing
        prices[region] = region_prices
    return {
        "date": (today or date.today()).isoformat(),
        "currency": "USD",
        "ondemand_note": (
            f"A pay-per-use price is for the usage in 'samples': {HOURS_PER_MONTH} hours when the "
            "unit is hours, otherwise the 'usage' of the sample (1 unit if it has none)."
        ),
        "samples": {s["id"]: {k: v for k, v in s.items() if k != "id"} for s in samples},
        "regions": prices,
    }


def diff(old: dict, new: dict) -> List[dict]:
    """List every price that is different between two snapshots."""
    changes: List[dict] = []
    for region, samples in new["regions"].items():
        for name, prices in samples.items():
            for billing, value in prices.items():
                before = old.get("regions", {}).get(region, {}).get(name, {}).get(billing)
                if before != value:
                    changes.append(
                        {"region": region, "sample": name, "billing": billing,
                         "before": before, "after": value}
                    )
    return changes


def latest_snapshot(directory: Path = SNAPSHOT_DIR) -> Optional[dict]:
    files = sorted(directory.glob("*.json"))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as handle:
        return json.load(handle)


def write_snapshot(snapshot: dict, directory: Path = SNAPSHOT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{snapshot['date']}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path

"""Price snapshots: the whole catalog quoted in several regions on one date."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .catalog import DATA_DIR, resolve, sample_id
from .client import (
    HOURS_PER_MONTH,
    MONTHLY,
    ON_DEMAND,
    ProductNotFound,
    Transport,
    quote,
)

SNAPSHOT_DIR = DATA_DIR / "snapshots"
BILLING_MODES = (MONTHLY, ON_DEMAND)


def take_snapshot(
    catalog: dict,
    regions: Iterable[str],
    transport: Optional[Transport] = None,
    today: Optional[date] = None,
) -> dict:
    """Quote every sample in every region. A product that is not offered becomes null."""
    result: Dict[str, Dict[str, Dict[str, Optional[float]]]] = {}
    for region in regions:
        region_prices: Dict[str, Dict[str, Optional[float]]] = {}
        for sample in catalog.get("samples", []):
            item = resolve(catalog, sample["product"], sample["spec"], sample.get("size_gb"))
            prices: Dict[str, Optional[float]] = {}
            for billing in BILLING_MODES:
                try:
                    prices[billing] = quote([item], region, billing, transport=transport).total
                except ProductNotFound:
                    prices[billing] = None
            region_prices[sample_id(sample)] = prices
        result[region] = region_prices
    return {
        "date": (today or date.today()).isoformat(),
        "currency": "USD",
        "ondemand_hours": HOURS_PER_MONTH,
        "regions": result,
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

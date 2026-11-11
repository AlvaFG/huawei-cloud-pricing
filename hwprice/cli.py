"""Command line: quote, verify, refresh and services."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .catalog import DATA_DIR, load_catalog, problems, resolve
from .client import (
    CALCULATOR_API,
    HOURS_PER_MONTH,
    MONTHLY,
    ON_DEMAND,
    Item,
    PricingError,
    ProductNotFound,
    fetch_json,
    quote,
)
from .snapshot import diff, latest_snapshot, take_snapshot, write_snapshot

DEFAULT_REGIONS = DATA_DIR / "regions.json"

# The example from Huawei's own price-inquiry guide: ECS c6.large.2 + 40 GB GP SSD,
# one month, CN North-Beijing4. Last seen at USD 34.11.
GUIDE_EXAMPLE = (
    Item("hws.service.type.ec2", "hws.resource.type.vm", "c6.large.2.linux"),
    Item("hws.service.type.ebs", "hws.resource.type.volume", "GPSSD", size_gb=40),
)
GUIDE_REGION = "cn-north-4"
GUIDE_LAST_SEEN = 34.11


def _region_ids() -> List[str]:
    with open(DEFAULT_REGIONS, encoding="utf-8") as handle:
        return [entry["id"] for entry in json.load(handle)["regions"]]


def cmd_quote(args: argparse.Namespace) -> int:
    item = resolve(load_catalog(), args.product, args.spec, args.size, args.quantity)
    try:
        result = quote([item], args.region, args.billing, args.hours)
    except ProductNotFound as error:
        print(f"not offered or unknown code in {args.region}: {error}")
        return 2
    print(f"{result.total:.2f} {result.currency}  ({args.product} {args.spec}, {args.region}, {args.billing})")
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    failed = False

    found = problems(load_catalog())
    if found:
        failed = True
        for line in found:
            print(f"FAIL catalog: {line}")
    else:
        print("ok   catalog is valid")

    try:
        result = quote(list(GUIDE_EXAMPLE), GUIDE_REGION)
        note = "" if abs(result.total - GUIDE_LAST_SEEN) < 0.005 else (
            f"  (price changed: it was {GUIDE_LAST_SEEN}; that is data, not a failure)")
        print(f"ok   guide example answers {result.total:.2f} {result.currency}{note}")
    except PricingError as error:
        failed = True
        print(f"FAIL guide example: {error}")

    try:
        quote([Item("hws.service.type.ec2", "hws.resource.type.vm", "no.such.spec.linux")], GUIDE_REGION)
        failed = True
        print("FAIL an unknown spec was accepted: the endpoint changed")
    except ProductNotFound:
        print("ok   an unknown spec is rejected (CBC.6006)")
    except PricingError as error:
        failed = True
        print(f"FAIL unknown-spec check: {error}")

    try:
        menu = fetch_json(f"{CALCULATOR_API}/menuInfo")
        count = len(menu.get("menuInfos", []))
        if count == 0:
            raise PricingError("menuInfo is empty")
        print(f"ok   menuInfo lists {count} categories")
    except PricingError as error:
        failed = True
        print(f"FAIL menuInfo: {error}")

    return 1 if failed else 0


def cmd_refresh(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    regions = args.regions or _region_ids()
    previous = latest_snapshot()
    snapshot = take_snapshot(catalog, regions)
    path = write_snapshot(snapshot)
    print(f"wrote {path}")
    if previous is None:
        print("first snapshot: nothing to compare")
        return 0
    changes = diff(previous, snapshot)
    if not changes:
        print("no price changed since the previous snapshot")
    for change in changes:
        print(f"{change['region']:14} {change['sample']:26} {change['billing']:8} "
              f"{change['before']} -> {change['after']}")
    return 0


def cmd_services(_: argparse.Namespace) -> int:
    menu = fetch_json(f"{CALCULATOR_API}/menuInfo")
    rows = []
    for parent in menu.get("menuInfos", []):
        for sub in parent.get("subCategoryLists") or []:
            for info in sub.get("categoryInfos") or []:
                rows.append({
                    "category": parent.get("parentCategoryName"),
                    "service": sub.get("categoryName"),
                    "urlPath": sub.get("urlPath"),
                    "cloudServiceType": info.get("cloudServiceType"),
                    "resourceType": info.get("resourceType"),
                })
    rows.sort(key=lambda row: (row["category"] or "", row["service"] or "", row["resourceType"] or ""))
    path = DATA_DIR / "services.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"source": f"{CALCULATOR_API}/menuInfo", "services": rows}, handle, indent=2)
        handle.write("\n")
    print(f"wrote {path} with {len(rows)} service/resource pairs")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hwprice", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("quote", help="price one catalog product in one region")
    one.add_argument("--region", required=True, help="region id, for example la-south-2")
    one.add_argument("--product", required=True, help="catalog product, for example ecs")
    one.add_argument("--spec", required=True, help="spec as in the console, for example s6.large.4")
    one.add_argument("--size", type=int, help="size in GB (volumes)")
    one.add_argument("--quantity", type=int, default=1)
    one.add_argument("--billing", choices=(MONTHLY, ON_DEMAND), default=MONTHLY)
    one.add_argument("--hours", type=int, default=HOURS_PER_MONTH, help="hours for ondemand")
    one.set_defaults(handler=cmd_quote)

    sub.add_parser("verify", help="check that the endpoints and the catalog still work").set_defaults(handler=cmd_verify)

    refresh = sub.add_parser("refresh", help="quote the whole catalog and save a snapshot")
    refresh.add_argument("--regions", nargs="+", help="region ids (default: data/regions.json)")
    refresh.set_defaults(handler=cmd_refresh)

    sub.add_parser("services", help="rebuild data/services.json from the calculator menu").set_defaults(handler=cmd_services)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except PricingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

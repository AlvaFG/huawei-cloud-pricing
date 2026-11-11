"""Command line: quote, specs, services, discover, audit, refresh, verify and docs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .client import (
    BILLING_MODES,
    CALCULATOR_API,
    HOURS_PER_MONTH,
    MONTHLY,
    ON_DEMAND,
    Item,
    PricingError,
    ProductNotFound,
    fetch_json,
    http_transport,
    quote,
)
from .discover import discover
from .report import render_services_page
from .snapshot import diff, latest_snapshot, load_samples, take_snapshot, write_snapshot
from .specs import (
    DATA_DIR,
    AmbiguousSpec,
    find_spec,
    item_for,
    load_services,
    load_specs,
    load_verification,
    resource_type_codes,
    service_table,
    type_key,
)

REGIONS_PATH = DATA_DIR / "regions.json"
DOCS_PAGE = DATA_DIR.parent / "docs" / "services.md"

# The example from Huawei's own price-inquiry guide: ECS c6.large.2 + 40 GB GP SSD,
# one month, CN North-Beijing4. Last seen at USD 34.11.
GUIDE_EXAMPLE = (
    Item("hws.service.type.ec2", "hws.resource.type.vm", "c6.large.2.linux"),
    Item("hws.service.type.ebs", "hws.resource.type.volume", "GPSSD", size=40),
)
GUIDE_REGION = "cn-north-4"
GUIDE_LAST_SEEN = 34.11


def _region_ids() -> List[str]:
    with open(REGIONS_PATH, encoding="utf-8") as handle:
        return [entry["id"] for entry in json.load(handle)["regions"]]


def _mode_info(service: str, record: dict, billing: str) -> Optional[dict]:
    outcome = load_verification().get("resource_types", {}).get(type_key(service, record["resourceType"]))
    return (outcome or {}).get("modes", {}).get(billing)


def resolve_sample(sample: dict, billing: str) -> Item:
    """Build the request line of a snapshot sample from the generated data."""
    service = sample["service"]
    record = find_spec(load_specs(service), sample["spec"], sample.get("resourceType"))
    return item_for(record, billing, size=sample.get("size"), usage_value=sample.get("usage"),
                    mode_info=_mode_info(service, record, billing))


def _quote_unlisted(args: argparse.Namespace) -> int:
    """Price a spec that Huawei's list does not have, sent exactly as typed."""
    if not args.resource_type:
        print("--unlisted needs --resource-type (see `python3 -m hwprice services --search ...`)", file=sys.stderr)
        return 2
    try:
        codes = resource_type_codes(service_table(load_services())[args.service], args.resource_type)
    except KeyError as error:
        print(error.args[0], file=sys.stderr)
        return 2
    item = Item(codes["cloudServiceType"], codes["resourceType"], args.spec, args.quantity, args.size)
    if args.billing == ON_DEMAND:
        item = Item(codes["cloudServiceType"], codes["resourceType"], args.spec, args.quantity, args.size,
                    usage_factor="Duration", usage_measure_id=4, usage_value=args.usage or HOURS_PER_MONTH)
    try:
        result = quote([item], args.region, args.billing)
    except ProductNotFound as error:
        print(f"not offered in {args.region}: {error}")
        return 2
    print(f"{result.total:.2f} {result.currency}  ({args.service} {args.spec}, {args.region}, {args.billing})")
    print("this spec is not in Huawei's spec list: it was sent as typed and its units were not verified")
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    try:
        record = find_spec(load_specs(args.service), args.spec, args.resource_type)
    except AmbiguousSpec as error:
        print(f"{error}:\n  " + "\n  ".join(error.candidates), file=sys.stderr)
        return 2
    except KeyError as error:
        if args.unlisted:
            return _quote_unlisted(args)
        print(f"{error.args[0]}\nA region can sell a spec that the list lacks: add --unlisted "
              "--resource-type <type> to send it as typed.", file=sys.stderr)
        return 2
    if args.billing not in record["billing"]:
        offered = ", ".join(record["billing"]) or "none"
        print(f"{record['spec']} is not sold as {args.billing}. It has: {offered}", file=sys.stderr)
        return 2
    try:
        info = _mode_info(args.service, record, args.billing)
        item = item_for(record, args.billing, args.quantity, args.size, args.usage, info, args.usage_factor)
        result = quote([item], args.region, args.billing)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except ProductNotFound as error:
        print(f"not offered in {args.region}: {error}")
        return 2
    print(f"{result.total:.2f} {result.currency}  ({args.service} {record['spec']}, {args.region}, {args.billing})")
    if args.billing == ON_DEMAND and item.usage_factor:
        print(f"for {item.usage_value:g} unit(s) of {item.usage_factor} (unit id {item.usage_measure_id})")
        factors = [u["factor"] for u in record.get("usage") or []]
        if len(factors) > 1:
            print(f"this spec is billed by {len(factors)} usage factors: {', '.join(factors)}; "
                  "choose one with --usage-factor")
    return 0


def cmd_specs(args: argparse.Namespace) -> int:
    try:
        specs = load_specs(args.service)
    except KeyError as error:
        print(error.args[0], file=sys.stderr)
        return 2
    needle = (args.search or "").lower()
    shown = 0
    for record in specs:
        if args.resource_type and record["resourceType"] != args.resource_type:
            continue
        if needle and needle not in f"{record['spec']} {record['description']}".lower():
            continue
        shown += 1
        if shown <= args.limit:
            print(f"{record['spec']:34} {','.join(record['billing']):24} {record['description'][:70]}")
    print(f"{shown} spec(s)" + (f", first {args.limit} shown" if shown > args.limit else ""))
    return 0


def cmd_services(args: argparse.Namespace) -> int:
    resource_types = load_verification().get("resource_types", {})
    needle = (args.search or "").lower()
    for service in load_services():
        if needle and needle not in f"{service['service']} {service['urlPath']} {service['category']}".lower():
            continue
        path = service["urlPath"]
        states = [t["status"] for key, t in resource_types.items() if key.startswith(f"{path}|")]
        verified = sum(1 for s in states if s == "verified")
        print(f"{path or '-':14} {service['service'][:46]:46} {verified}/{len(states)} verified  [{service['category']}]")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    discover(fetch_json, http_transport, only=args.only, resume=args.resume)
    print("done. Next: python3 -m hwprice docs")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Run again the request that verification recorded for each resource type, mode and factor."""
    wanted = set(args.service) if args.service else None
    problems = changed = checked = 0
    for key, outcome in sorted(load_verification().get("resource_types", {}).items()):
        path, resource_type = key.split("|", 1)
        if wanted and path not in wanted:
            continue
        for mode, info in outcome.get("modes", {}).items():
            variants = list((info.get("factors") or {}).items()) if mode == ON_DEMAND else [(None, info)]
            for factor, variant in variants:
                if not variant.get("ok"):
                    continue
                checked += 1
                label = f"{path} {resource_type} {mode}" + (f" {factor}" if factor else "")
                record = find_spec(load_specs(path), variant["spec"], resource_type)
                item = item_for(record, mode, size=100 if variant.get("sized") else None,
                                mode_info=info, usage_factor=factor)
                try:
                    result = quote([item], variant["region"], mode)
                except PricingError as error:
                    problems += 1
                    print(f"FAIL {label}: {error}")
                    continue
                if abs(result.total - variant["amount"]) > 0.005:
                    changed += 1
                    print(f"changed {label}: {variant['amount']} -> {result.total}")
    print(f"checked {checked} verified combinations: {problems} failed, {changed} with a different price")
    return 1 if problems else 0


def cmd_verify(_: argparse.Namespace) -> int:
    failed = False

    try:
        services = load_services()
        verification = load_verification()
        missing = [s["urlPath"] for s in services if s["urlPath"] and not (DATA_DIR / "specs" / f"{s['urlPath']}.json").exists()]
        if missing or not verification.get("resource_types"):
            raise ValueError(f"data is incomplete (specs missing for: {', '.join(missing[:5]) or 'none'})")
        print(f"ok   data: {len(services)} services, {len(verification['resource_types'])} resource types")
    except (OSError, KeyError, ValueError) as error:
        failed = True
        print(f"FAIL data: {error}")

    try:
        from .client import quote as price
        result = price(list(GUIDE_EXAMPLE), GUIDE_REGION)
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
        count = len(fetch_json(f"{CALCULATOR_API}/menuInfo").get("menuInfos", []))
        if count == 0:
            raise PricingError("menuInfo is empty")
        print(f"ok   menuInfo lists {count} categories")
    except PricingError as error:
        failed = True
        print(f"FAIL menuInfo: {error}")

    return 1 if failed else 0


def cmd_refresh(args: argparse.Namespace) -> int:
    regions = args.regions or _region_ids()
    previous = latest_snapshot()
    snapshot = take_snapshot(load_samples(), regions, resolve_sample)
    path = write_snapshot(snapshot)
    print(f"wrote {path}")
    if previous is None:
        print("first snapshot: nothing to compare")
        return 0
    changes = diff(previous, snapshot)
    if not changes:
        print("no price changed since the previous snapshot")
    for change in changes:
        print(f"{change['region']:14} {change['sample']:34} {change['billing']:8} "
              f"{change['before']} -> {change['after']}")
    return 0


def cmd_docs(_: argparse.Namespace) -> int:
    DOCS_PAGE.write_text(render_services_page(load_services(), load_verification()), encoding="utf-8")
    print(f"wrote {DOCS_PAGE}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hwprice", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("quote", help="price one spec of one service in one region")
    one.add_argument("--region", required=True, help="region id, for example la-south-2")
    one.add_argument("--service", required=True, help="service key from `services`, for example ecs")
    one.add_argument("--spec", required=True, help="spec code, for example s6.large.4.linux")
    one.add_argument("--resource-type", help="needed when a spec code exists in two resource types, or with --unlisted")
    one.add_argument("--unlisted", action="store_true",
                     help="send a spec that Huawei's list does not have, exactly as typed (needs --resource-type)")
    one.add_argument("--size", type=float, help="size, for products priced by size (GB for disks)")
    one.add_argument("--usage", type=float, help="usage for pay-per-use (default: 730 hours, or 1 unit)")
    one.add_argument("--usage-factor", help="what a pay-per-use spec is billed by, when it has several")
    one.add_argument("--quantity", type=int, default=1)
    one.add_argument("--billing", choices=BILLING_MODES, default=MONTHLY)
    one.set_defaults(handler=cmd_quote)

    specs = sub.add_parser("specs", help="list the specs of a service")
    specs.add_argument("--service", required=True)
    specs.add_argument("--search", help="text to look for in the spec code or its description")
    specs.add_argument("--resource-type")
    specs.add_argument("--limit", type=int, default=40)
    specs.set_defaults(handler=cmd_specs)

    services = sub.add_parser("services", help="list the services and how many resource types are verified")
    services.add_argument("--search")
    services.set_defaults(handler=cmd_services)

    found = sub.add_parser("discover", help="rebuild services, specs and verification (slow, about 15 minutes)")
    found.add_argument("--only", nargs="+", help="only these services (the --service keys)")
    found.add_argument("--resume", action="store_true", help="skip the services that already have a verification")
    found.set_defaults(handler=cmd_discover)

    audit = sub.add_parser("audit", help="run again the verified requests and report what broke or changed")
    audit.add_argument("--service", nargs="+")
    audit.set_defaults(handler=cmd_audit)

    sub.add_parser("verify", help="check that the endpoints and the data still work").set_defaults(handler=cmd_verify)

    refresh = sub.add_parser("refresh", help="quote the reference products and save a snapshot")
    refresh.add_argument("--regions", nargs="+", help="region ids (default: data/regions.json)")
    refresh.set_defaults(handler=cmd_refresh)

    sub.add_parser("docs", help="regenerate docs/services.md from the data").set_defaults(handler=cmd_docs)
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

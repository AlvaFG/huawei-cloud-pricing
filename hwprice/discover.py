"""Discover every service and spec Huawei lists, and test that each one can be priced.

Nothing here is written by hand. The services come from the calculator menu, the specs
from the calculator's own product list, and a resource type counts as priceable only
after the price endpoint answered a real request for it.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from .client import (
    CALCULATOR_API,
    HOUR_MEASURE_ID,
    HOURS_PER_MONTH,
    MONTHLY,
    ON_DEMAND,
    YEARLY,
    Item,
    PricingError,
    ProductNotFound,
    Quote,
    Transport,
    quote,
)
from .specs import SERVICES_PATH, SPECS_DIR, VERIFICATION_PATH, load_verification, type_key

# The catalog's own list prices match this region, so it is tried first.
REFERENCE_REGION = "ap-southeast-1"
# Most products answer in the first region. The rest are tried only for what failed, so that a
# product sold only in some regions (for example in mainland China) is not reported as broken.
REGIONS_TRIED = (
    REFERENCE_REGION, "la-south-2", "ap-southeast-3", "cn-north-4", "cn-southwest-2",
    "cn-east-3", "sa-brazil-1", "af-south-1", "eu-west-101",
)
MAX_SPECS_TRIED = 2
MAX_FACTORS = 8
SIZE_PROBE = 100

_MODE_BY_PLAN = {"MONTHLY": MONTHLY, "YEARLY": YEARLY, "ONDEMAND": ON_DEMAND}

GetJson = Callable[[str, Optional[Dict[str, str]]], dict]


def parse_menu(menu: dict) -> List[dict]:
    """The services of the calculator menu, each with its resource types."""
    services: List[dict] = []
    for parent in menu.get("menuInfos", []):
        for sub in parent.get("subCategoryLists") or []:
            pairs = [
                {"cloudServiceType": info.get("cloudServiceType"), "resourceType": info.get("resourceType")}
                for info in sub.get("categoryInfos") or []
            ]
            services.append({
                "category": parent.get("parentCategoryName"),
                "service": sub.get("categoryName"),
                "urlPath": sub.get("urlPath"),
                "hasCalculator": bool(sub.get("hasCalculator")),
                "resourceTypes": pairs,
            })
    services.sort(key=lambda s: ((s["category"] or ""), (s["service"] or "")))
    return services


def _has_codes(entry: dict) -> bool:
    return all(entry.get(key) for key in ("cloudServiceType", "resourceType", "resourceSpecCode"))


def count_without_codes(product_info: dict) -> int:
    """Entries of the product list that are not specs (for example OS image descriptions)."""
    return sum(1 for entries in (product_info.get("product") or {}).values()
               for entry in entries if not _has_codes(entry))


def extract_specs(product_info: dict) -> List[dict]:
    """Flatten the product list of one service into one record per spec.

    The list repeats a spec once for each usage factor it is billed by (a messaging spec can
    be billed by calls, e-mails and SMS), so the entries of a spec are merged into one record.
    An entry without the service, resource and spec codes cannot be priced and is not a
    spec; ``count_without_codes`` says how many were left out.
    """
    merged: Dict[Tuple[str, str, str], dict] = {}
    for entries in (product_info.get("product") or {}).values():
        for entry in entries:
            if not _has_codes(entry):
                continue
            key = (entry["cloudServiceType"], entry["resourceType"], entry["resourceSpecCode"])
            record = merged.get(key)
            if record is None:
                record = {
                    "cloudServiceType": key[0],
                    "resourceType": key[1],
                    "spec": key[2],
                    "description": entry.get("productSpecSysDesc") or "",
                    "billing": [],
                }
                merged[key] = record
            elif not record["description"] and entry.get("productSpecSysDesc"):
                record["description"] = entry["productSpecSysDesc"]
            for plan in entry.get("planList") or []:
                mode = _MODE_BY_PLAN.get(plan.get("billingMode"))
                if mode is None:
                    continue
                if mode not in record["billing"]:
                    record["billing"].append(mode)
                if mode == ON_DEMAND:
                    use = {"factor": plan.get("usageFactor"), "unit": plan.get("measureUnit"),
                           "measure": plan.get("usageMeasureId")}
                    if use["factor"] and use not in record.setdefault("usage", []):
                        record["usage"].append(use)
                elif plan.get("periodNum") == 1 and plan.get("amount") is not None:
                    record.setdefault("list", {}).setdefault(mode, plan["amount"])
    return list(merged.values())


def _templates(mode: str, spec: dict, factor: Optional[str] = None) -> Iterator[Item]:
    """The requests to try for one spec, most likely first."""
    base = dict(
        cloud_service_type=spec["cloudServiceType"],
        resource_type=spec["resourceType"],
        spec=spec["spec"],
    )
    sizes: Tuple[Optional[float], ...] = (None, SIZE_PROBE)
    if mode != ON_DEMAND:
        for size in sizes:
            yield Item(size=size, **base)
        return
    usage = next(u for u in spec["usage"] if u["factor"] == factor)
    units: List[int] = []
    for unit in (usage.get("unit"), usage.get("measure"), HOUR_MEASURE_ID):
        if unit is not None and unit not in units:
            units.append(unit)
    for unit in units:
        value = HOURS_PER_MONTH if unit == HOUR_MEASURE_ID else 1
        for size in sizes:
            yield Item(size=size, usage_factor=usage["factor"], usage_measure_id=unit,
                       usage_value=value, **base)


_MEASURE = re.compile(r"measure\((\d+)\)")


def _try_template(
    template: Item, region: str, mode: str, transport: Optional[Transport], last: str
) -> Tuple[Optional[Quote], Item, str]:
    """Price one request. If the endpoint names the unit it wanted, try that unit once.

    A sized product that is not measured in GB answers, for example,
    "Convert from resource spec size measure(17) to resource spec size measure(15)".
    The numbers are the unit that was sent and the unit the product expects.
    """
    tried = {template.size_measure_id}
    queue = [template]
    while queue:
        item = queue.pop(0)
        try:
            return quote([item], region, mode, transport=transport), item, last
        except ProductNotFound as error:
            return None, item, str(error)
        except PricingError as error:
            last = str(error)
            if item.size is None:
                continue
            for number in (int(n) for n in _MEASURE.findall(last)):
                if number not in tried:
                    tried.add(number)
                    queue.append(replace(item, size_measure_id=number))
    return None, template, last


def _verify_candidates(
    candidates: Sequence[dict],
    mode: str,
    transport: Optional[Transport],
    regions: Sequence[str],
    today: Optional[date],
    factor: Optional[str] = None,
) -> dict:
    """Price a few specs in one billing mode (and usage factor) until one answers."""
    last = "not tried"
    for spec in candidates[:MAX_SPECS_TRIED]:
        contradicted = False
        for region in regions:
            if contradicted:
                break
            for template in _templates(mode, spec, factor):
                result, item, last = _try_template(template, region, mode, transport, last)
                if result is None:
                    if last.startswith("CBC.6006"):
                        break  # another size or unit will not help: try the next region
                    continue
                listed = (spec.get("list") or {}).get(mode)
                comparable = listed is not None and region == REFERENCE_REGION
                # A catalog list price is per unit: for a product priced by size, compare the price
                # of one unit, so that a wrong unit (GB where the product counts something else)
                # is caught and not only a request that the endpoint accepts.
                per_unit = result.total / item.size if item.size else result.total
                tolerance = max(0.005 / (item.size or 1), abs(listed or 0) * 0.001)
                if comparable and abs(per_unit - listed) >= tolerance:
                    # The endpoint answered, but not with the number the catalog lists for this
                    # spec: the request is not the one the product needs. Do not call it verified.
                    last = (f"the endpoint answered {per_unit:g} per unit but the catalog lists {listed:g} "
                            f"for {spec['spec']}")
                    # No other variant or region can be compared with the list: drop this spec.
                    contradicted = True
                    break
                answer = {
                    "ok": True,
                    "region": region,
                    "spec": spec["spec"],
                    "amount": result.total,
                    "verified_on": (today or date.today()).isoformat(),
                }
                if item.size is not None:
                    answer["sized"] = True
                    answer["sizeMeasureId"] = item.size_measure_id
                if mode == ON_DEMAND:
                    answer["usageFactor"] = item.usage_factor
                    answer["usageMeasureId"] = item.usage_measure_id
                if comparable:
                    answer["listPrice"] = listed
                    answer["matchesList"] = True
                return answer
    return {"ok": False, "reason": last}


def verify_mode(
    specs: Sequence[dict],
    mode: str,
    transport: Optional[Transport],
    regions: Sequence[str] = REGIONS_TRIED,
    today: Optional[date] = None,
) -> dict:
    """Verify one billing mode of a resource type.

    Pay-per-use is verified once for each usage factor the specs are billed by (up to
    MAX_FACTORS); the answer is the first one that worked, with all of them under ``factors``.
    """
    if mode != ON_DEMAND:
        candidates = [s for s in specs if mode in s["billing"]]
        if not candidates:
            return {"ok": False, "reason": "no plan"}
        return _verify_candidates(candidates, mode, transport, regions, today)

    factors: List[str] = []
    for spec in specs:
        for usage in spec.get("usage") or []:
            if usage["factor"] not in factors:
                factors.append(usage["factor"])
    if not factors:
        return {"ok": False, "reason": "no plan"}
    results: Dict[str, dict] = {}
    for factor in factors[:MAX_FACTORS]:
        candidates = [s for s in specs if any(u["factor"] == factor for u in s.get("usage") or [])]
        results[factor] = _verify_candidates(candidates, mode, transport, regions, today, factor)
    first = next((info for info in results.values() if info["ok"]), next(iter(results.values())))
    outcome = dict(first)
    outcome["factors"] = results
    if len(factors) > MAX_FACTORS:
        outcome["factorsNotChecked"] = len(factors) - MAX_FACTORS
    return outcome


def verify_type(
    specs: Sequence[dict],
    transport: Optional[Transport] = None,
    regions: Sequence[str] = REGIONS_TRIED,
    today: Optional[date] = None,
) -> dict:
    """Verify every billing mode that some spec of this resource type offers."""
    modes: Dict[str, dict] = {}
    for mode in (MONTHLY, YEARLY, ON_DEMAND):
        outcome = verify_mode(specs, mode, transport, regions, today)
        if outcome.get("reason") == "no plan":
            continue
        modes[mode] = outcome
    if not modes:
        status = "no-plans"
    elif any(m["ok"] for m in modes.values()):
        status = "verified" if all(m["ok"] for m in modes.values()) else "partial"
    else:
        status = "unverified"
    return {"status": status, "specs": len(specs), "modes": modes}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _write_specs(url_path: str, specs: List[dict], directory: Path, skipped: int = 0) -> None:
    """One spec per line, so a price or a new spec shows as a small diff.

    ``skipped`` counts the entries of the product list that are not specs (they have no codes).
    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = ",\n".join("    " + json.dumps(s, ensure_ascii=False, separators=(", ", ": ")) for s in specs)
    extra = f'  "skipped_without_codes": {skipped},\n' if skipped else ""
    text = f'{{\n  "urlPath": {json.dumps(url_path)},\n{extra}  "specs": [\n{lines}\n  ]\n}}\n'
    (directory / f"{url_path}.json").write_text(text, encoding="utf-8")
    (directory / f"{url_path}.json").write_text(text, encoding="utf-8")


def discover(
    get_json: GetJson,
    transport: Optional[Transport] = None,
    only: Optional[Iterable[str]] = None,
    resume: bool = False,
    today: Optional[date] = None,
    log: Callable[[str], None] = print,
    specs_dir: Path = SPECS_DIR,
    services_path: Path = SERVICES_PATH,
    verification_path: Path = VERIFICATION_PATH,
) -> dict:
    """Rebuild the service list, the spec lists and the verification of what is priceable.

    The progress is saved after every service, so a crash loses at most one service.
    With ``resume`` a service that already has a verification is skipped.
    """
    services = parse_menu(get_json(f"{CALCULATOR_API}/menuInfo", None))
    _write_json(services_path, {"source": f"{CALCULATOR_API}/menuInfo", "services": services})
    wanted = set(only) if only else None
    verification = load_verification(verification_path)
    types = verification.setdefault("resource_types", {})

    for service in services:
        path = service["urlPath"]
        if not path or (wanted is not None and path not in wanted):
            continue
        if resume and any(key.startswith(f"{path}|") for key in types):
            continue
        info = get_json(f"{CALCULATOR_API}/productInfo", {"urlPath": path})
        specs = extract_specs(info)
        _write_specs(path, specs, specs_dir, count_without_codes(info))
        for stale in [key for key in types if key.startswith(f"{path}|")]:
            del types[stale]
        groups: Dict[Tuple[str, str], List[dict]] = {}
        for spec in specs:
            groups.setdefault((spec["cloudServiceType"], spec["resourceType"]), []).append(spec)
        verdicts = []
        for (cloud_type, resource_type), group in sorted(groups.items()):
            outcome = verify_type(group, transport, today=today)
            outcome["cloudServiceType"] = cloud_type
            types[type_key(path, resource_type)] = outcome
            verdicts.append(outcome["status"])
        verification["generated"] = (today or date.today()).isoformat()
        _write_json(verification_path, verification)
        log(f"{path:12} {len(specs):5} specs, {len(groups):2} resource types: {', '.join(verdicts) or 'none'}")

    return verification

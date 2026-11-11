"""Read the generated data: services, specs and the result of verifying them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .client import GB_MEASURE_ID, HOUR_MEASURE_ID, HOURS_PER_MONTH, ON_DEMAND, Item

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPECS_DIR = DATA_DIR / "specs"
SERVICES_PATH = DATA_DIR / "services.json"
VERIFICATION_PATH = DATA_DIR / "verification.json"


class AmbiguousSpec(Exception):
    """More than one spec matches what was asked."""

    def __init__(self, message: str, candidates: List[str]):
        super().__init__(message)
        self.candidates = candidates


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_services(path: Path = SERVICES_PATH) -> List[dict]:
    return _load(path)["services"]


def load_specs(url_path: str, directory: Path = SPECS_DIR) -> List[dict]:
    path = directory / f"{url_path}.json"
    if not path.exists():
        raise KeyError(f"no specs for service {url_path!r}; run `python3 -m hwprice services`")
    return _load(path)["specs"]


def load_verification(path: Path = VERIFICATION_PATH) -> dict:
    if not path.exists():
        return {"resource_types": {}}
    return _load(path)


def type_key(url_path: str, resource_type: str) -> str:
    return f"{url_path}|{resource_type}"


def find_spec(specs: List[dict], spec: str, resource_type: Optional[str] = None) -> dict:
    """Find one spec by the code shown in the console.

    A code that is a whole word of a longer one also matches (``s6.large.4`` finds
    ``s6.large.4.linux``) as long as only one spec does.
    """
    pool = [s for s in specs if resource_type in (None, s["resourceType"])]
    exact = [s for s in pool if s["spec"] == spec]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        kinds = sorted({s["resourceType"] for s in exact})
        raise AmbiguousSpec(f"{spec!r} exists in several resource types; pass --resource-type", kinds)
    partial = [s for s in pool if s["spec"].startswith(spec + ".")]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise KeyError(f"no spec {spec!r}; search with `python3 -m hwprice specs --service <name> --search <text>`")
    names = sorted(s["spec"] for s in partial)
    raise AmbiguousSpec(f"{spec!r} matches several specs; pick one", names[:12])


def item_for(
    record: dict,
    billing: str,
    quantity: int = 1,
    size: Optional[float] = None,
    usage_value: Optional[float] = None,
    mode_info: Optional[dict] = None,
    usage_factor: Optional[str] = None,
) -> Item:
    """Turn a spec record into a request line, using what verification learned about it.

    For pay-per-use a spec can be billed by several usage factors (calls, e-mails, GB...).
    ``usage_factor`` picks one; without it the first verified factor is used.
    """
    info = mode_info or {}
    if billing == ON_DEMAND and usage_factor is not None:
        # What verification learned about that factor, if it was checked.
        info = (info.get("factors") or {}).get(usage_factor) or {}
    if info.get("sized") and size is None:
        raise ValueError("this product is priced by size: pass --size")

    fields = dict(
        cloud_service_type=record["cloudServiceType"],
        resource_type=record["resourceType"],
        spec=record["spec"],
        quantity=quantity,
    )
    if size is not None:
        fields["size"] = size
        fields["size_measure_id"] = info.get("sizeMeasureId", GB_MEASURE_ID)

    if billing == ON_DEMAND:
        usages = record.get("usage") or []
        if not usages:
            raise ValueError("this spec has no pay-per-use plan")
        factor = usage_factor or info.get("usageFactor") or usages[0]["factor"]
        entry = next((u for u in usages if u["factor"] == factor), None)
        if entry is None:
            raise ValueError(f"this spec is not billed by {factor!r}; it is billed by: "
                             + ", ".join(u["factor"] for u in usages))
        measure = info.get("usageMeasureId")
        if measure is None:
            measure = entry.get("unit") if entry.get("unit") is not None else entry.get("measure")
        if usage_value is None:
            usage_value = HOURS_PER_MONTH if measure == HOUR_MEASURE_ID else 1
        fields["usage_factor"] = factor
        fields["usage_measure_id"] = measure
        fields["usage_value"] = usage_value
    return Item(**fields)


def resource_type_codes(service: dict, resource_type: str) -> Dict[str, str]:
    """The two codes of a resource type of a service. The short name (``rds.vm``) is enough."""
    pairs = service.get("resourceTypes") or []
    wanted = resource_type if resource_type.startswith("hws.") else f"hws.resource.type.{resource_type}"
    for pair in pairs:
        if pair["resourceType"] == wanted:
            return {"cloudServiceType": pair["cloudServiceType"], "resourceType": pair["resourceType"]}
    known = ", ".join(sorted(p["resourceType"].replace("hws.resource.type.", "") for p in pairs)) or "none"
    raise KeyError(f"{service['urlPath']} has no resource type {resource_type!r}; it has: {known}")


def service_table(services: List[dict]) -> Dict[str, dict]:
    """Index the services by urlPath."""
    return {s["urlPath"]: s for s in services if s.get("urlPath")}

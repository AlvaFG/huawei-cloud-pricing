"""The catalog of product codes that have been checked against the endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .client import Item

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_PATH = DATA_DIR / "catalog.json"

REQUIRED_PRODUCT_KEYS = ("description", "cloudServiceType", "resourceType")


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def resolve(
    catalog: dict,
    product: str,
    spec: str,
    size_gb: Optional[int] = None,
    quantity: int = 1,
) -> Item:
    """Turn a catalog product and a spec name into a request line.

    The spec is what you read in the console (for example ``s6.large.4``). Some
    products need a suffix in the request (ECS adds ``.linux``).
    """
    products: Dict[str, dict] = catalog["products"]
    if product not in products:
        raise KeyError(f"unknown product {product!r}; known: {', '.join(sorted(products))}")
    definition = products[product]
    suffix = definition.get("specSuffix", "")
    code = spec if not suffix or spec.endswith(suffix) else spec + suffix
    if definition.get("sized") and size_gb is None:
        raise ValueError(f"{product} is priced by size: pass size_gb")
    return Item(
        cloud_service_type=definition["cloudServiceType"],
        resource_type=definition["resourceType"],
        spec=code,
        quantity=quantity,
        size_gb=size_gb if definition.get("sized") else None,
    )


def sample_id(sample: dict) -> str:
    """A stable name for a sample line, such as ``evs:SSD:100gb``."""
    parts = [sample["product"], sample["spec"]]
    if sample.get("size_gb") is not None:
        parts.append(f"{sample['size_gb']}gb")
    return ":".join(parts)


def problems(catalog: dict) -> List[str]:
    """Return what is wrong with a catalog (an empty list means it is valid)."""
    found: List[str] = []
    products = catalog.get("products", {})
    for name, definition in products.items():
        for key in REQUIRED_PRODUCT_KEYS:
            if not definition.get(key):
                found.append(f"product {name!r} is missing {key!r}")
    for sample in catalog.get("samples", []):
        if sample.get("product") not in products:
            found.append(f"sample {sample!r} points to an unknown product")
        elif products[sample["product"]].get("sized") and sample.get("size_gb") is None:
            found.append(f"sample {sample!r} needs size_gb")
    return found

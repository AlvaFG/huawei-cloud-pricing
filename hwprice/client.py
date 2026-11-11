"""HTTP client for the public Huawei Cloud price calculator.

The calculator at https://www.huaweicloud.com/intl/en-us/pricing/calculator.html calls
a price endpoint that needs no login. This module builds the same request and reads
the same response. It is not an official API and Huawei may change it at any time.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

PRICE_ENDPOINT = (
    "https://portal-intl.huaweicloud.com/api/cbc/global/rest/BSS/billing/"
    "ratingservice/v2/inquiry/resource"
)
CALCULATOR_API = (
    "https://portal-intl.huaweicloud.com/api/calculator/rest/cbc/"
    "portalcalculatornodeservice/v4/api"
)
USER_AGENT = "huawei-cloud-pricing/0.1 (+https://github.com/AlvaFG/huawei-cloud-pricing)"

# Be a polite client: never send more than four requests per second.
MIN_INTERVAL_SECONDS = 0.25

SITE_CODE = "HWC"
MONTHLY = "monthly"
ON_DEMAND = "ondemand"
HOURS_PER_MONTH = 730
GB_MEASURE_ID = 17
HOUR_MEASURE_ID = 4

# A transport takes the request body and returns the decoded JSON response.
Transport = Callable[[dict], dict]


class PricingError(Exception):
    """The endpoint answered with an error or an unexpected body."""


class ProductNotFound(PricingError):
    """The service, resource type or spec code does not exist in that region (CBC.6006)."""


@dataclass(frozen=True)
class Item:
    """One product line of a price request."""

    cloud_service_type: str
    resource_type: str
    spec: str
    quantity: int = 1
    size_gb: Optional[int] = None


@dataclass(frozen=True)
class Quote:
    """The answer for one request: a total and the amount of each line."""

    region: str
    billing: str
    total: float
    currency: str
    lines: Sequence[float]


def build_payload(
    items: Sequence[Item],
    region: str,
    billing: str = MONTHLY,
    hours: int = HOURS_PER_MONTH,
) -> dict:
    """Build the request body the calculator sends.

    monthly: a one-month subscription (chargingMode 0, periodType 2).
    ondemand: pay-per-use for ``hours`` hours (chargingMode 1, periodType 4).
    """
    if billing not in (MONTHLY, ON_DEMAND):
        raise ValueError(f"billing must be '{MONTHLY}' or '{ON_DEMAND}', got {billing!r}")
    if not items:
        raise ValueError("at least one item is required")

    product_infos: List[Dict[str, object]] = []
    for index, item in enumerate(items, start=1):
        info: Dict[str, object] = {
            "id": str(index),
            "cloudServiceType": item.cloud_service_type,
            "productNum": item.quantity,
            "resourceSpecCode": item.spec,
            "resourceType": item.resource_type,
        }
        if item.size_gb is not None:
            info["resourceSize"] = item.size_gb
            # The API really spells this key without the second "r".
            info["resouceSizeMeasureId"] = GB_MEASURE_ID
        if billing == ON_DEMAND:
            info["usageFactor"] = "Duration"
            info["usageMeasureId"] = HOUR_MEASURE_ID
            info["usageValue"] = hours
        product_infos.append(info)

    is_monthly = billing == MONTHLY
    return {
        "chargingMode": 0 if is_monthly else 1,
        "periodNum": 1,
        "periodType": 2 if is_monthly else 4,
        "regionId": region,
        "siteCode": SITE_CODE,
        "subscriptionNum": 1,
        "productInfos": product_infos,
    }


_last_call = 0.0


def _throttle() -> None:
    global _last_call
    wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _error_message(raw: str) -> str:
    match = re.search(r"CBC\.\d+:[^\"\]]+", raw)
    return match.group(0) if match else raw[:200]


def http_transport(payload: dict) -> dict:
    """POST the payload to the price endpoint, at most four times per second."""
    _throttle()
    request = urllib.request.Request(
        PRICE_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        if "CBC.6006" in raw:
            raise ProductNotFound(_error_message(raw)) from error
        raise PricingError(f"HTTP {error.code}: {_error_message(raw)}") from error
    except urllib.error.URLError as error:
        raise PricingError(f"cannot reach the price endpoint: {error.reason}") from error


def fetch_json(url: str) -> dict:
    """GET a calculator catalog endpoint (same throttle, same user agent)."""
    _throttle()
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise PricingError(f"cannot read {url}: {error}") from error


def quote(
    items: Sequence[Item],
    region: str,
    billing: str = MONTHLY,
    hours: int = HOURS_PER_MONTH,
    transport: Optional[Transport] = None,
) -> Quote:
    """Price the items in a region. Raises ProductNotFound for an unknown code."""
    send = transport or http_transport
    body = send(build_payload(items, region, billing, hours))
    amount = body.get("amount")
    if amount is None:
        raise PricingError(f"the response has no amount: {json.dumps(body)[:200]}")
    lines = [
        float(line["amount"])
        for line in body.get("productRatingResult") or []
        if line.get("amount") is not None
    ]
    return Quote(
        region=region,
        billing=billing,
        total=float(amount),
        currency=str(body.get("currency", "USD")),
        lines=lines,
    )

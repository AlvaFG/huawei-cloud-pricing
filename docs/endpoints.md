# Endpoints

All of these were read from the JavaScript of the public price calculator
(`https://www.huaweicloud.com/intl/en-us/pricing/calculator.html`) and tested without a
login. They are not a documented API. If one stops working, run `python3 -m hwprice verify`
and follow [updating.md](updating.md).

The host for the international site is `portal-intl.huaweicloud.com`. The China site uses
`portal.huaweicloud.com` with the same paths.

## Price

| | |
|---|---|
| Method and URL | `POST https://portal-intl.huaweicloud.com/api/cbc/global/rest/BSS/billing/ratingservice/v2/inquiry/resource` |
| Needs a login | No |
| Body | JSON, see [payloads.md](payloads.md) |
| Used by | `hwprice quote`, `hwprice refresh` |

One endpoint prices both monthly subscriptions and pay-per-use. The difference is in the body.
The region is a field of the body, not part of the URL.

## Catalog

| URL (under `/api/calculator/rest/cbc/portalcalculatornodeservice/v4/api/`) | What it returns |
|---|---|
| `menuInfo` | Every service the calculator shows, with its `cloudServiceType` and `resourceType` codes. About 170 KB. Rebuilt into `data/services.json` by `hwprice services` |
| `productInfo` | The specs of a few products: ECS flavors, volume types and elastic IP. About 5 MB. Most services are not here, so their spec codes have to be captured from the browser ([discovering-codes.md](discovering-codes.md)) |
| `config` | JavaScript with the calculator's own settings (period lists and similar). Not price data |

Other paths appear in the calculator's JavaScript (`export/productlist`, `quoting_item`, `share/*`,
`formExport`, `language`). They look like features of the page itself, and this project does not use
them. Two more price paths under `/api/cbc/user/rest/...` appear to be for signed-in sessions; they were
not tested.

## The official API

Huawei documents price inquiry in its Business Support System API, which needs IAM credentials
with billing permission and uses `snake_case` fields (`product_infos`, `cloud_service_type`):

- `ListRateOnPeriodDetail`: yearly and monthly prices.
- `ListOnDemandResourceRatings`: pay-per-use prices.
- `ListServiceTypes`, `ListResourceTypes`, `ListResourceSpecs`: the codes.

The calculator's request has the same meaning with `camelCase` names. If you have credentials,
the official API is the stable way to find the codes this project is missing.

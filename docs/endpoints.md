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
| Used by | `hwprice quote`, `hwprice refresh`, `hwprice discover`, `hwprice audit` |

One endpoint prices monthly and yearly subscriptions and pay-per-use, for every service.
The difference is in the body. The region is a field of the body, not part of the URL.

## Catalog

All under `https://portal-intl.huaweicloud.com/api/calculator/rest/cbc/portalcalculatornodeservice/v4/api/`.

| Path | What it returns |
|---|---|
| `menuInfo` | Every service of the calculator menu: category, name, `urlPath`, whether it has a calculator page, and its `cloudServiceType` and `resourceType` codes. Becomes `data/services.json` |
| `productInfo?urlPath=<service>` | **The complete list of specs of one service**: every `resourceSpecCode`, its description, the billing modes it has (monthly, yearly, pay-per-use, reserved) and, for pay-per-use, the usage factor and unit. It also carries a list price. Becomes `data/specs/<urlPath>.json` |
| `config?urlPath=<service>` | JavaScript with the form of that service's calculator page: which fields it asks for and the patterns of its spec codes. Useful to understand a service, not needed to price it |

Without `urlPath`, `productInfo` answers for ECS.

### The list price in `productInfo`

Each plan in `productInfo` has an `amount`. It is the price in one default region (it equals the price of
`ap-southeast-1`, Hong Kong, in every check that was made), not in all regions. For another region only the
price endpoint knows the number. `hwprice` uses the list price as a cross-check, not as an answer: see
`matchesList` in [updating.md](updating.md).

### Services without a calculator page

`menuInfo` marks some services with `hasCalculator: false` (for example SWR, SMN or the backup services).
`productInfo` still lists their specs and the price endpoint prices some of them. They are in the data like
any other service. [services.md](services.md) says how far each one was verified.

### Other paths

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
the official API is the stable way to price; this project exists for the case where you do not.

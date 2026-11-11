# Finding the codes of a product

To price a product you need three codes: `cloudServiceType`, `resourceType` and the spec
(`resourceSpecCode`). An unknown code answers `CBC.6006`.

## 1. The service and resource codes

They are all in `data/services.json`, rebuilt from the calculator menu:

```bash
python3 -m hwprice services
grep -i -A3 '"service": "NAT Gateway"' data/services.json
```

## 2. The spec code, from the browser (about a minute)

The calculator sends the spec in its own request, so you can copy it.

1. Open <https://www.huaweicloud.com/intl/en-us/pricing/calculator.html> and choose the service.
2. Open the developer tools (F12) and go to the **Network** tab.
3. Set the product the way you want it (region, size, billing mode).
4. Find the request called `resource` (use the filter), open **Payload** and copy `resourceSpecCode`
   and any extra fields, such as `usageFactor`.
5. Test it:

```bash
python3 - <<'PY'
from hwprice.client import Item, quote
item = Item("hws.service.type.natgateway", "hws.resource.type.natgateway", "<spec you copied>")
print(quote([item], "la-south-2"))
PY
```

Huawei's own guide shows the same steps with screenshots:
`https://support.huaweicloud.com/intl/en-us/api-oce/csdp_faq_062501.html` (monthly) and
`.../csdp_faq_062502.html` (pay-per-use).

## 3. With credentials: the official API

If you have an IAM user with billing read permission, call `ListServiceTypes`, `ListResourceTypes`
and `ListResourceSpecs` of the Business Support System API. They list every code without opening a
browser.

## 4. Pay-by-traffic and other usage-based products

A product billed by use (traffic, requests) needs a `usageFactor` and a `usageMeasureId`. Capture them
as in step 2, with the calculator set to **Pay-per-use**. `hwprice` only builds the `Duration` usage
today; a product with another factor needs a small change in `build_payload` and a test.

## Add it to the catalog

1. Add the product to `products` in `data/catalog.json` and a line to `samples`.
2. Remove it from `pending` if it was there.
3. `python3 -m unittest discover -s tests`, `python3 -m hwprice verify`, `python3 -m hwprice refresh`.
4. Commit the catalog and the new snapshot.

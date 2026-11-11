# Finding the codes of a product

You rarely need to. `python3 -m hwprice discover` reads Huawei's own list of services and specs,
so every spec Huawei lists is already in `data/`:

```bash
python3 -m hwprice services --search nat        # which services match
python3 -m hwprice specs --service nat          # their spec codes and billing modes
```

This page is for when something is missing or wrong.

## The three codes

A price request needs `cloudServiceType`, `resourceType` and `resourceSpecCode`. An unknown code answers
`CBC.6006`. In the data they are in `data/specs/<service>.json`, one spec per line.

## A spec is listed but cannot be priced

Look at its resource type in [services.md](services.md), "Not fully verified". The usual reasons:

- **Not sold in the regions that were tried.** The verification tries `ap-southeast-1`, `la-south-2` and
  `ap-southeast-3`. Try another region: `quote --region <id> ...`.
- **The product needs a size or a unit the verification did not guess.** Disks, bandwidth and some databases
  are priced by size. Capture the real request, as below.
- **The service is not sold through the calculator.** The list has it, the price endpoint does not.

## Capture the real request from the browser (about a minute)

The calculator sends the exact fields in its own request, so you can copy them.

1. Open <https://www.huaweicloud.com/intl/en-us/pricing/calculator.html> and choose the service.
2. Open the developer tools (F12) and go to the **Network** tab.
3. Set the product the way you want it (region, size, billing mode).
4. Find the request called `resource` (use the filter), open **Payload** and look at the line of your product:
   `resourceSpecCode`, `resourceSize` and `resouceSizeMeasureId`, `usageFactor`, `usageMeasureId`, `usageValue`.
5. Test it from Python:

```python
from hwprice.client import Item, quote
item = Item("hws.service.type.natgateway", "hws.resource.type.natgateway", "natgateway_small")
print(quote([item], "la-south-2"))
```

Huawei's own guide shows the same steps with screenshots:
`https://support.huaweicloud.com/intl/en-us/api-oce/csdp_faq_062501.html` (monthly) and
`.../csdp_faq_062502.html` (pay-per-use).

## What the units mean

`usageMeasureId` says what `usageValue` counts. Seen so far: `4` hours, `10` GB, `14` a count, `17` GB for a
size. The spec list has, for each pay-per-use spec, its usage factor and unit, and `hwprice` uses them.

## With credentials: the official API

If you have an IAM user with billing read permission, `ListServiceTypes`, `ListResourceTypes` and
`ListResourceSpecs` of the Business Support System API list every code without opening a browser.

## If you fix something

Teach the code, not only the data: if a product needs a field that `build_payload` does not send, change it
and add a test in `tests/test_client.py`. Then `python3 -m unittest discover -s tests`,
`python3 -m hwprice discover --only <service>`, `python3 -m hwprice docs`, and commit `data/` and
`docs/services.md` together.

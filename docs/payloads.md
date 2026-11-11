# Request and response format

`hwprice/client.py` builds these bodies (`build_payload`). The shapes match the requests the
calculator sends; the page's own help article shows the same ones.

## Subscription: monthly or yearly

```json
{
  "chargingMode": 0,
  "periodNum": 1,
  "periodType": 2,
  "regionId": "la-south-2",
  "siteCode": "HWC",
  "subscriptionNum": 1,
  "productInfos": [
    {
      "id": "1",
      "cloudServiceType": "hws.service.type.ec2",
      "productNum": 1,
      "resourceSpecCode": "s6.large.4.linux",
      "resourceType": "hws.resource.type.vm"
    },
    {
      "id": "2",
      "cloudServiceType": "hws.service.type.ebs",
      "productNum": 1,
      "resourceSpecCode": "GPSSD",
      "resourceType": "hws.resource.type.volume",
      "resourceSize": 100,
      "resouceSizeMeasureId": 17
    }
  ]
}
```

`periodType` is `2` for a month and `3` for a year, with `periodNum` 1.

## Pay-per-use

Same shape, with `chargingMode` 1, `periodType` 4 and, on every line, what is consumed:

```json
{ "usageFactor": "Duration", "usageMeasureId": 4, "usageValue": 730 }
```

The usage depends on the service. A server is priced by hours of `Duration` (unit `4`); a public IP's traffic by
`upflow` in GB (unit `10`); other services by a count, a number of calls or a size. Each spec in `data/specs/` lists
its `usage` (`factor` and `unit`), and `hwprice` sends them. `usageValue` is how many units: 730 hours is one
average month.

## Fields

| Field | Meaning |
|---|---|
| `chargingMode` | `0` subscription, `1` pay-per-use |
| `periodType` / `periodNum` | `2` month, `3` year, `4` hour (the official API also lists `0` day). `periodNum` is how many |
| `regionId` | Region, for example `la-south-2`. See [regions-and-prices.md](regions-and-prices.md) |
| `siteCode` | `HWC` |
| `productInfos[].id` | Any string, unique inside the request. The response repeats it |
| `cloudServiceType`, `resourceType` | The service and resource codes. See `data/services.json` |
| `resourceSpecCode` | The spec, as in `data/specs/`. ECS adds the OS to the flavor (`s6.large.4.linux`). A RDS spec ending in `.ha` is the primary/standby version |
| `productNum` | Quantity of that line |
| `resourceSize` and `resouceSizeMeasureId` | For products priced by size: the amount, and its unit (`17` is GB). **The API spells the key `resouceSizeMeasureId`, without the second r.** The code keeps that spelling on purpose |
| `usageFactor`, `usageMeasureId`, `usageValue` | For pay-per-use: what is consumed, its unit and how much |

## Which products need a size

The product list does not say. A product priced by size answers an error such as `resourceSpecSize is null or
empty` when the size is missing, so `discover` retries with a size and records what worked in
`data/verification.json` (`sized`, `sizeMeasureId`). `quote` reads it from there and asks you for `--size`.

## Response

```json
{
  "amount": 34.11,
  "officialWebsiteAmount": 34.11,
  "discountAmount": 0.0,
  "originalAmount": 34.11,
  "currency": "USD",
  "productRatingResult": [
    { "id": "1", "amount": 29.79 },
    { "id": "2", "amount": 4.32 }
  ]
}
```

`amount` is the total of the request and `productRatingResult` has one entry per line, in the same
order. The client reads `amount`, `currency` and the amount of each line.

## Errors

An unknown service, resource type or spec answers HTTP 500 with:

```json
{"exceptionId":"CBC.6006","descArgs":["CBC.6006:Can not find product <spec>"]}
```

The client raises `ProductNotFound` for it. The message names the spec but the cause can also be the
service or the resource type, or a product that the region does not offer. Other `CBC.xxxx` codes mean the
request is incomplete or has a wrong unit; `discover` uses them to find the right fields.

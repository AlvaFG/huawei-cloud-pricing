---
name: huawei-cloud-pricing
description: Use when you need the price of a Huawei Cloud product in a region, want to compare regions or billing modes, or need to refresh, verify or extend the price catalog and snapshots of this repository.
---

# Huawei Cloud pricing

This repository prices Huawei Cloud products with the same public endpoint the price calculator uses,
and keeps dated snapshots of the answers. Read `README.md` first if you have not.

## Rules

- **Prices come from the endpoint, never from memory.** Run a command and read its output. If a command
  fails, say so; do not estimate.
- **Never invent a code.** `cloudServiceType`, `resourceType` and the spec must come from
  `data/services.json`, `data/catalog.json` or a request captured from the calculator. An unknown code
  answers `CBC.6006`.
- **Be a polite client.** The client already waits 250 ms between requests. Do not run requests in parallel
  and do not call the endpoint in a loop that the task does not need.
- **Never write credentials, account IDs or project IDs** into any file.
- **Snapshots are history.** Add a new one with `refresh`; never edit an old one.

## Price something

```bash
python3 -m hwprice quote --region <region-id> --product <product> --spec <spec> [--size GB] [--billing monthly|ondemand] [--hours N] [--quantity N]
```

Products are the keys of `products` in `data/catalog.json` (`ecs`, `evs`, `rds-postgresql`, `cce-cluster`,
`eip`). Region ids are in `data/regions.json`. The answer is in USD, list price, without tax.

- If the output says `not offered or unknown code`, the region does not sell it or a code is wrong. Check
  the newest snapshot: a `null` there means "not offered in that region".
- To compare regions without new requests, read the newest file in `data/snapshots/`.
- Pay-per-use over a month is `--billing ondemand` with the default 730 hours.

## Update the data

1. `python3 -m hwprice verify`. If it exits with 1, stop and read `docs/updating.md`, section "When verify
   fails". Do not refresh until you understand why.
2. `python3 -m hwprice refresh`. It writes `data/snapshots/<date>.json` and prints each price that changed.
3. Summarise the changes for the user: product, region, billing mode, old and new price. Flag any change of
   more than 20% and any product that stopped being offered.
4. If the user asked for it, commit with `data: refresh price snapshot <date>`.

`python3 -m hwprice services` rebuilds `data/services.json` from the calculator menu. Run it when asked to
check for new services.

## Add a product

Follow `docs/discovering-codes.md`. In short: take the service and resource codes from `data/services.json`,
capture the spec from a calculator request (or ask the user for it), test it with `hwprice.client.quote`,
add it to `data/catalog.json`, remove it from `pending`, run `python3 -m unittest discover -s tests`,
`verify` and `refresh`.

## What is not covered

Taxes, discounts, contracts, reserved instances and real billing. For those the user needs the console or
the billing API with credentials. Say so when the question needs it.

---
name: huawei-cloud-pricing
description: Use when you need the price of any Huawei Cloud service in any region, want to compare regions or billing modes, or need to refresh, verify or extend the data of this repository (services, specs, verification, snapshots).
---

# Huawei Cloud pricing

This repository prices every Huawei Cloud service listed by the public price calculator, using the same
endpoint the calculator uses, and keeps the list of services and specs in `data/`. Read `README.md` first
if you have not.

## Rules

- **Prices come from the endpoint, never from memory.** Run a command and read its output. If a command
  fails, say so; do not estimate.
- **Never invent a code.** Services, resource types and spec codes come from `data/` (Huawei's own lists).
  `python3 -m hwprice services` and `specs` search them. An unknown code answers `CBC.6006`.
- **Say what was verified.** `data/verification.json` and `docs/services.md` say, per resource type and
  billing mode, whether a real price request worked. Do not present an unverified resource type as priced.
- **Be a polite client.** The client already waits 250 ms between requests. Do not run requests in parallel
  and do not loop over the endpoint unless the task needs it.
- **Never write credentials, account IDs or project IDs** into any file.
- **Snapshots are history.** Add a new one with `refresh`; never edit an old one.

## Price something

1. Find the service key: `python3 -m hwprice services --search <text>`.
2. Find the spec: `python3 -m hwprice specs --service <key> --search <text>`. It lists the billing modes
   each spec has.
3. Quote it:

```bash
python3 -m hwprice quote --service <key> --spec <spec> --region <region-id> \
  [--billing monthly|yearly|ondemand] [--size N] [--usage N] [--quantity N] [--resource-type RT]
```

- Region ids are in `data/regions.json`. The answer is USD, list price, no tax.
- `--size` is needed for products priced by size (disks, bandwidth); the command says so when it is.
- Pay-per-use prices a usage: 730 hours for an hourly unit, otherwise 1 unit. Pass `--usage` for another amount
  (for example GB of traffic). The command prints which unit it used.
- `not offered in <region>`: the region does not sell it. The newest snapshot shows `null` for the same thing.
- A spec code that is a whole word of a longer one is accepted when unique (`s6.large.4` finds
  `s6.large.4.linux`). If two match, the command lists them.
- To compare regions without new requests, read the newest file in `data/snapshots/`. It covers the reference
  products of `data/samples.json`, not every spec.

## Update the data

1. `python3 -m hwprice verify`. If it exits with 1, stop and read `docs/updating.md`, "When something
   fails". Do not refresh until you understand why.
2. `python3 -m hwprice audit` runs again every verified request. Report any FAIL and any price change.
3. `python3 -m hwprice refresh` writes `data/snapshots/<date>.json` and prints each price that changed.
4. `python3 -m hwprice docs` rebuilds `docs/services.md`.
5. Summarise for the user: product, region, billing mode, old and new price. Flag a change of more than 20%
   and any product that stopped being offered.
6. If the user asked for it, commit with `data: refresh price snapshot <date>`.

`python3 -u -m hwprice discover` rebuilds everything (about 40 minutes). Use `--only <service>` for one
service and `--resume` after an interruption. Run it when asked to look for new services or specs, then
`docs`, then the tests.

## Fix or extend

Follow `docs/discovering-codes.md`. A product that cannot be priced usually needs a field `build_payload`
does not send: capture the real request from the calculator, change the code, add a test, rediscover that
service and regenerate `docs/services.md`.

## What is not covered

Taxes, discounts, contracts, reserved instances and real billing. For those the user needs the console or
the billing API with credentials. Say so when the question needs it.

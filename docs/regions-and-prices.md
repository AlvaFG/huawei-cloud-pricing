# Regions and prices

The price endpoint is the same for every region. The region goes in the body as `regionId`, and
the answer changes with it.

## What changes

- **The price of the same product.** A server flavor can cost very different amounts in two regions.
  A cluster management fee changes too. Some products cost the same everywhere.
- **What is offered.** A region may sell a server and a disk but not a managed cluster or a managed
  database. The endpoint answers `CBC.6006` for what a region does not sell, and a snapshot stores
  that as `null`.

Do not read prices from this page. They are data and they change: open the newest file in
`data/snapshots/`, which has the reference products of `data/samples.json` in every region of
`data/regions.json`.

## The catalog's list price is one region only

Each plan in Huawei's own product list has an `amount`. It is the price in one default region (it equals
`ap-southeast-1` in every comparison that was made), so it cannot be used for the others. `hwprice` keeps it
only to cross-check the endpoint: see "What is checked" in [updating.md](updating.md).

## Compare regions

```bash
# One product in two regions
python3 -m hwprice quote --region la-south-2  --service ecs --spec s6.large.4.linux
python3 -m hwprice quote --region sa-brazil-1 --service ecs --spec s6.large.4.linux
```

```python
import json, glob
snapshot = json.load(open(sorted(glob.glob("data/snapshots/*.json"))[-1]))
for region, products in snapshot["regions"].items():
    print(region, products["ecs:s6.large.4.linux"]["monthly"])
```

A product that is not in `data/samples.json` has no stored price: ask the endpoint with `quote`.

## Region ids

`data/regions.json` has the ids that were checked. The calculator lists more regions than that file.
To add one, pick its id from the region list of the console, run
`python3 -m hwprice quote --region <id> ...` and, if it answers, add it to the file.

Region ids are not always what the name suggests, so check them against the console URL or the
endpoint list of the service, not against a guess.

## Pay-per-use against a subscription

For the same server, pay-per-use over 730 hours costs more than one month of subscription, and a yearly
subscription costs less per month again. A subscription commits you for its period, so a team that is still
sizing a system often starts pay-per-use. `quote --billing monthly|yearly|ondemand` lets you compare, and
`--usage` sets the amount of a pay-per-use.

A pay-per-use price is for the usage you ask for: 730 hours when the unit is hours, otherwise 1 unit unless
you pass `--usage`. The output says which unit it used.

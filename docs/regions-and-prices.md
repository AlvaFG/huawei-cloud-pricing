# Regions and prices

The price endpoint is the same for every region. The region goes in the body as `regionId`, and
the answer changes with it.

## What changes

- **The price of the same product.** A server flavor can cost very different amounts in two regions.
  A cluster management fee changes too.
- **What is offered.** A region may sell a server and a disk but not a managed cluster or a managed
  database. The endpoint answers `CBC.6006` for what a region does not sell, and a snapshot stores
  that as `null`.

Do not read prices from this page. They are data and they change: open the newest file in
`data/snapshots/`, which has every catalog product in every region of `data/regions.json`.

## Compare regions

```bash
# One product in two regions
python3 -m hwprice quote --region la-south-2  --product ecs --spec s6.large.4
python3 -m hwprice quote --region sa-brazil-1 --product ecs --spec s6.large.4
```

```python
import json, glob
snapshot = json.load(open(sorted(glob.glob("data/snapshots/*.json"))[-1]))
for region, products in snapshot["regions"].items():
    print(region, products["ecs:s6.large.4"]["monthly"])
```

## Region ids

`data/regions.json` has the ids that were checked. The calculator lists more regions than that file.
To add one, pick its id from the region list of the console, run
`python3 -m hwprice quote --region <id> ...` and, if it answers, add it to the file.

Region ids are not always what the name suggests, so check them against the console URL or the
endpoint list of the service, not against a guess.

## Pay-per-use against a monthly subscription

For the same server, pay-per-use over 730 hours costs more than one month of subscription. Subscriptions
are cheaper per month but commit you for the period, so a team that is still sizing a system often
starts pay-per-use. `quote --billing ondemand` and `--hours` let you compare.

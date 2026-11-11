# huawei-cloud-pricing

Look up the price of any Huawei Cloud service from the command line, in any region, and keep the whole list of services and specs in Git.

[Leer en español](README.es.md)

Huawei's price calculator asks a public endpoint for every number it shows. This project sends the same request, so a script can answer "how much does this cost in that region?" without clicking through the web page. It also copies Huawei's own list of services and specs, tests that each one can really be priced, and stores dated price snapshots, so you can see how prices change over time.

> **Unofficial.** This project is not affiliated with or endorsed by Huawei. It reads the endpoints the public calculator uses, which are not a documented API and may change without notice. Prices are list prices in USD: no taxes, no discounts, no contract terms. Always confirm a price in the console before you buy.

## Coverage

All numbers come from `data/` and are rebuilt by the tool, not typed by hand. [docs/services.md](docs/services.md) has the table for every service.

- **105** services of the calculator menu, with **270** resource types and **8,612** specs, copied from Huawei's own lists.
- **226** resource types were priced against the endpoint in every billing mode they have. **31** could not be priced at all and **5** only in some billing modes; they are listed with the reason.
- **227** answers were also compared with the list price in Huawei's catalog and matched.

"Verified" means that one or two specs of the resource type were priced for real, not that every spec was. What was not verified is listed, not hidden.

## What you get

- **A command line** to find a service, list its specs and price one in any region and billing mode.
- **Every service Huawei lists** in `data/services.json`, and **every spec** in `data/specs/<service>.json`.
- **A verification record** (`data/verification.json`) of what answered and with which request, and a **coverage page** that shows it.
- **Dated price snapshots** (`data/snapshots/`) of reference products in several regions. The Git history of this folder is the price history.
- **A `verify` and an `audit` command** that tell you when the endpoints or the data stop working.
- **GitHub Actions** that refresh the snapshot every week and rediscover the services every month, each opening a pull request with what changed.
- **An agent skill** (`.claude/skills/huawei-cloud-pricing/`) so an AI coding agent can quote prices and update the data by following written instructions.

Python 3.9 or newer. No packages to install.

## Quick start

```bash
git clone https://github.com/AlvaFG/huawei-cloud-pricing.git
cd huawei-cloud-pricing

python3 -m hwprice services --search nat          # find a service
python3 -m hwprice specs --service nat            # its specs and billing modes

# One NAT gateway for one month in LA-Santiago
python3 -m hwprice quote --region la-south-2 --service nat --spec natgateway_small

# A server, pay-per-use for a month (730 hours)
python3 -m hwprice quote --region la-south-2 --service ecs --spec s6.large.4.linux --billing ondemand

# A 100 GB disk
python3 -m hwprice quote --region la-south-2 --service evs --spec GPSSD --size 100
```

```
57.30 USD  (nat natgateway_small, la-south-2, monthly)
43.80 USD  (ecs s6.large.4.linux, la-south-2, ondemand)
for 730 unit(s) of Duration (unit id 4)
9.40 USD  (evs GPSSD, la-south-2, monthly)
```

A spec code that matches more than one spec lists them instead of guessing:

```
$ python3 -m hwprice quote --region la-south-2 --service ecs --spec s6.large.4
's6.large.4' matches several specs; pick one:
  s6.large.4.byol
  s6.large.4.linux
```

A product that a region does not offer is reported instead of guessed:

```
not offered in sa-argentina-1: CBC.6006:Can not find product cce.s1.small
```

## Does the price depend on the region?

Yes. The endpoint is the same for every region: the region is a field of the request (`regionId`). The price of the same product changes with it, and some products are not offered everywhere. See [docs/regions-and-prices.md](docs/regions-and-prices.md).

## Commands

| Command | What it does |
|---|---|
| `services` | List the services and how many resource types are verified |
| `specs` | List the specs of a service, with their billing modes |
| `quote` | Price one spec in one region: monthly, yearly or pay-per-use |
| `verify` | Check that the endpoints and the data still work. Exit code 1 means something broke |
| `audit` | Run again every verified request, report failures and price changes |
| `refresh` | Price the reference products in every region, save a snapshot and print what changed |
| `discover` | Rebuild services, specs and verification from Huawei's lists (about 30 minutes) |
| `docs` | Rebuild the coverage page |

## Limits you should know

- **The spec list is the default region's.** A region can sell a spec that the list does not have (RDS for PostgreSQL `medium.2` is sold in LA-Santiago but is not listed). `quote --unlisted --resource-type <type>` sends it as typed.
- **Pay-per-use prices a usage.** A server is priced by hours, other services by GB, calls or a count. `quote` prints which unit it used and `--usage` changes the amount. A spec billed by several factors needs `--usage-factor`.
- **Some resource types cannot be priced through the calculator.** They are listed in [docs/services.md](docs/services.md) with the reason.

## Keep it up to date

There are three ways, from least to most automatic. Details in [docs/updating.md](docs/updating.md).

1. **By hand:** `python3 -m hwprice verify && python3 -m hwprice audit && python3 -m hwprice refresh`, then commit.
2. **With an AI agent:** point it at this repository and ask it to update the prices. The skill tells it which commands to run, how to read the result and how to fix what fails.
3. **Automatically:** [`refresh.yml`](.github/workflows/refresh.yml) runs every Monday and [`discover.yml`](.github/workflows/discover.yml) on the first day of each month. Enable *Allow GitHub Actions to create and approve pull requests* in the repository settings.

## How it works

```
hwprice/client.py    builds the request and reads the answer (stdlib only, 4 requests per second at most)
hwprice/discover.py  reads Huawei's service and spec lists and tests that each one can be priced
hwprice/specs.py     finds a spec and builds the request line for it
hwprice/snapshot.py  prices the reference products in many regions and compares two snapshots
hwprice/report.py    writes the coverage page
hwprice/cli.py       the commands above
data/                services, specs, verification, reference products, regions and snapshots
docs/                endpoints, request format, regions, how to find codes, how to update, coverage
```

## Be a polite client

The endpoint serves a public web page. This client waits at least 250 ms between requests and identifies itself in the `User-Agent`. Please keep it that way, do not run it in tight loops and read Huawei's terms for the site you query.

## Contributing

Pull requests that fix a resource type, add regions or reference products, or improve the documentation are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Never include credentials, account IDs or private data.

## License

[MIT](LICENSE)

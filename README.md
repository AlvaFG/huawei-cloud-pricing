# huawei-cloud-pricing

Look up Huawei Cloud prices from the command line, keep a dated history of them in Git, and update the whole thing with one command.

[Leer en español](README.es.md)

Huawei's price calculator asks a public endpoint for every number it shows. This project sends the same request, so a script can answer "how much does this cost in that region?" without clicking through the web page. It also stores the answers, so you can see how prices change over time.

> **Unofficial.** This project is not affiliated with or endorsed by Huawei. It reads the endpoints the public calculator uses, which are not a documented API and may change without notice. Prices are list prices in USD: no taxes, no discounts, no contract terms. Always confirm a price in the console before you buy.

## What you get

- **A command line** to price one product in one region.
- **A catalog** of product codes that were checked against the endpoint (`data/catalog.json`) and a list of all the 298 service and resource codes the calculator knows (`data/services.json`).
- **Dated price snapshots** (`data/snapshots/`) for the same products in several regions. The Git history of this folder is the price history.
- **A `verify` command** that tells you when the endpoint or the catalog stops working.
- **A weekly GitHub Action** that refreshes the snapshot and opens a pull request with what changed.
- **An agent skill** (`.claude/skills/huawei-cloud-pricing/`) so an AI coding agent can quote prices and update the data by following written instructions.

Python 3.9 or newer. No packages to install.

## Quick start

```bash
git clone https://github.com/AlvaFG/huawei-cloud-pricing.git
cd huawei-cloud-pricing

# One server for one month in LA-Santiago
python3 -m hwprice quote --region la-south-2 --product ecs --spec s6.large.4

# A 100 GB disk
python3 -m hwprice quote --region la-south-2 --product evs --spec GPSSD --size 100

# The same server, pay-per-use for a month (730 hours)
python3 -m hwprice quote --region la-south-2 --product ecs --spec s6.large.4 --billing ondemand
```

```
31.54 USD  (ecs s6.large.4, la-south-2, monthly)
9.40 USD  (evs GPSSD, la-south-2, monthly)
43.80 USD  (ecs s6.large.4, la-south-2, ondemand)
```

A product that a region does not offer is reported instead of guessed:

```
not offered or unknown code in sa-argentina-1: CBC.6006:Can not find product cce.s1.small
```

## Does the price depend on the region?

Yes. The endpoint is the same for every region: the region is a field of the request (`regionId`). The price of the same product changes with it, and some products are not offered everywhere. Compare regions in `data/snapshots/` or run `python3 -m hwprice refresh`. See [docs/regions-and-prices.md](docs/regions-and-prices.md).

## Commands

| Command | What it does |
|---|---|
| `quote` | Price one catalog product in one region (monthly or pay-per-use) |
| `verify` | Check that the endpoints and the catalog still work. Exit code 1 means something broke |
| `refresh` | Price the whole catalog in every region of `data/regions.json`, save a snapshot and print what changed since the last one |
| `services` | Rebuild `data/services.json` from the calculator menu |

## Keep it up to date

There are three ways, from least to most automatic. Details in [docs/updating.md](docs/updating.md).

1. **By hand:** `python3 -m hwprice verify && python3 -m hwprice refresh`, then commit the new snapshot.
2. **With an AI agent:** point it at this repository and ask it to update the prices. The skill tells it which commands to run, how to read the result and how to add a product it does not know.
3. **Automatically:** [`.github/workflows/refresh.yml`](.github/workflows/refresh.yml) runs every Monday and opens a pull request with the price changes. Enable *Allow GitHub Actions to create and approve pull requests* in the repository settings.

## Add a product

The catalog has the products that were verified. The calculator knows many more, and the missing piece is usually a spec code. [docs/discovering-codes.md](docs/discovering-codes.md) shows how to copy it from the browser in a minute, and `data/catalog.json` lists what is still missing (for example, the NAT Gateway spec code).

## How it works

```
hwprice/client.py    builds the request and reads the answer (stdlib only, 4 requests per second at most)
hwprice/catalog.py   turns "ecs s6.large.4" into the codes the endpoint expects
hwprice/snapshot.py  prices the catalog in many regions and compares two snapshots
hwprice/cli.py       the commands above
data/                catalog, regions, service list and snapshots
docs/                endpoints, request format, regions, how to find codes, how to update
```

## Be a polite client

The endpoint serves a public web page. This client waits at least 250 ms between requests and identifies itself in the `User-Agent`. Please keep it that way, do not run it in tight loops and read Huawei's terms for the site you query.

## Contributing

Pull requests that add products to the catalog, regions or documentation are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Never include credentials, account IDs or private data.

## License

[MIT](LICENSE)

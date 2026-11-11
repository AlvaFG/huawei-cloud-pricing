# Contributing

Thank you for helping. The most useful contributions are:

- a **product** the catalog does not have yet (see `pending` in `data/catalog.json`);
- a **region** that is missing from `data/regions.json`;
- a fix when `python3 -m hwprice verify` fails because Huawei changed something;
- clearer documentation.

## Before you open a pull request

```bash
python3 -m unittest discover -s tests -v   # offline, must pass
python3 -m hwprice verify                  # needs internet, must exit 0
```

If you add a product, also run `python3 -m hwprice refresh` and include the new snapshot, so the pull request shows its prices.

## Adding a product to the catalog

1. Find the three codes (`cloudServiceType`, `resourceType`, spec). [docs/discovering-codes.md](docs/discovering-codes.md) explains how.
2. Add the product to `products` in `data/catalog.json`, and one or two lines to `samples`.
3. Price it for real: a code the endpoint rejects answers `CBC.6006`. Only add codes that answered a price.
4. Remove it from `pending` if it was there.

## Rules

- No credentials, access keys, account IDs or project IDs in code, data or screenshots.
- Keep the polite client: at least 250 ms between requests, no parallel requests.
- The code uses the Python standard library only. Please do not add dependencies.
- Prices are data, not documentation: do not copy them into the docs. Link to a snapshot.

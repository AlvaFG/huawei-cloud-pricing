# Contributing

Thank you for helping. The most useful contributions are:

- fixing a resource type that [docs/services.md](docs/services.md) lists under "Not fully verified";
- a **region** that is missing from `data/regions.json`;
- a fix when `python3 -m hwprice verify` fails because Huawei changed something;
- reference products for `data/samples.json`;
- clearer documentation.

## Before you open a pull request

```bash
python3 -m unittest discover -s tests -v   # offline, must pass
python3 -m hwprice verify                  # needs internet, must exit 0
```

## The data is generated, not typed

`data/services.json`, `data/specs/` and `data/verification.json` are written by `python3 -m hwprice discover`
and `docs/services.md` by `python3 -m hwprice docs`. Please do not edit them by hand: change the code and
generate them again, so that the next run does not undo your change. A pull request that changes generated
files should include the code change that explains it.

To fix one service:

```bash
python3 -m hwprice discover --only <service>
python3 -m hwprice docs
python3 -m unittest discover -s tests
```

## Adding a reference product

`data/samples.json` lists the products that `refresh` quotes in every region. Add an entry with an `id`, the
`service` key, the `spec` and the `billing` modes. The data test checks that the spec exists and that each
billing mode was verified, so you cannot add a product that cannot be priced.

## Rules

- No credentials, access keys, account IDs or project IDs in code, data or screenshots.
- Keep the polite client: at least 250 ms between requests, no parallel requests.
- The code uses the Python standard library only. Please do not add dependencies.
- Prices are data, not documentation: do not copy them into the docs. Link to a snapshot.
- Only claim what was checked. If you could not verify something, say so in the pull request.

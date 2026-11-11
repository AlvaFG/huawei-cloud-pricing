# Keeping the data up to date

Prices change, Huawei adds specs, and the endpoint can change. There are three levels of care, and you
can mix them.

## What is checked, and how

| What | How it is known | How it is kept fresh |
|---|---|---|
| Which services and specs exist | Copied from Huawei's own menu and product list, not typed by hand | `hwprice discover` (monthly in CI) |
| That a resource type can be priced | The price endpoint answered a real request for one or two of its specs, in each billing mode | `hwprice discover`, then `hwprice audit` runs the same requests again |
| That the answer is the right number | In the reference region (`ap-southeast-1`) the endpoint is compared with the catalog's list price. `matchesList: true` means they are equal | Same |
| Reference prices by region | `data/snapshots/<date>.json`, from `data/samples.json` | `hwprice refresh` (weekly in CI) |

"Verified" means that sample specs of a resource type were priced for real. It does not mean that every one of
the thousands of specs was. A spec that is listed but sold in no region will answer `CBC.6006`.

## 1. By hand

```bash
python3 -m hwprice verify      # are the endpoints and the data fine?
python3 -m hwprice audit       # do the verified requests still work? did a price change?
python3 -m hwprice refresh     # new reference snapshot; prints what changed
git add data && git commit -m "data: refresh price snapshot"
```

For new services or specs, and to rebuild the verification (about 40 minutes, it is polite and slow):

```bash
python3 -u -m hwprice discover          # everything
python3 -m hwprice discover --only nat  # one service
python3 -m hwprice discover --resume    # continue after an interruption
python3 -m hwprice docs                 # rebuild docs/services.md
```

`verify` exits with 1 if something broke. A different price for the guide example is not a failure: it is
reported as a note, because prices are meant to change.

## 2. With an AI agent

The skill in `.claude/skills/huawei-cloud-pricing/SKILL.md` has the instructions. Any agent that can run
shell commands and read a file can follow them. A prompt that works:

> Read `.claude/skills/huawei-cloud-pricing/SKILL.md` and update the prices. Run `verify` first. If it
> passes, run `audit` and `refresh` and summarise what changed. If anything fails, find out why before
> changing anything.

## 3. Automatically

Two workflows open pull requests, which you review like any other change:

- `refresh.yml` runs every Monday: `verify`, `audit`, `refresh` and `docs`.
- `discover.yml` runs on the first day of each month: it rediscovers every service and spec.

Both need *Settings, Actions, General, Allow GitHub Actions to create and approve pull requests*. A large
change in one product is worth a look at the console before you merge it.

## When something fails

| What fails | Likely cause | What to do |
|---|---|---|
| `verify`: the guide example or the price endpoint | The endpoint moved or the body changed | Capture a fresh request in the browser ([discovering-codes.md](discovering-codes.md)), compare it with `build_payload` in `hwprice/client.py`, fix it and add a test |
| `verify`: an unknown spec is rejected | The endpoint now accepts bad codes | Prices could be wrong. Do not refresh until you understand it |
| `verify`: menuInfo | The catalog URL changed | Look for the new path in the calculator's JavaScript and update `CALCULATOR_API` |
| `verify`: data | A file is missing or empty | Run `discover` again |
| `audit`: FAIL | A verified request no longer works | The product or its units changed. Run `discover --only <service>` and read the diff |
| `audit`: changed | A price moved | That is data. Run `refresh` |

## Snapshots are history

Never edit a snapshot. Each file in `data/snapshots/` is the answer of one date, and the Git history
of the folder is the history of prices.

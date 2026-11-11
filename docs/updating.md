# Keeping the data up to date

Prices change and Huawei can change the endpoint. There are three levels of care, and you can mix them.

## 1. By hand

```bash
python3 -m hwprice verify      # are the endpoints and the catalog fine?
python3 -m hwprice refresh     # new snapshot; prints what changed
git add data && git commit -m "data: refresh price snapshot"
```

`verify` exits with 1 if something broke. A different price for the guide example is not a failure: it is
reported as a note, because prices are meant to change.

## 2. With an AI agent

The skill in `.claude/skills/huawei-cloud-pricing/SKILL.md` has the instructions. Any agent that can run
shell commands and read a file can follow them. A prompt that works:

> Read `.claude/skills/huawei-cloud-pricing/SKILL.md` and update the prices. Run `verify` first. If it
> passes, run `refresh` and summarise what changed. If it fails, find out why before changing anything.

To teach the agent a new product, give it the name and ask it to add it to the catalog following
[discovering-codes.md](discovering-codes.md).

## 3. Automatically

`.github/workflows/refresh.yml` runs every Monday, executes `verify` and `refresh`, and opens a pull
request if a price changed. For this to work, enable *Settings, Actions, General, Allow GitHub Actions to
create and approve pull requests*. Review the pull request like any other: a large change in one product
is worth a look at the console before you merge it.

## When `verify` fails

| What fails | Likely cause | What to do |
|---|---|---|
| `guide example` or the price endpoint | The endpoint moved or the body changed | Capture a fresh request in the browser ([discovering-codes.md](discovering-codes.md), step 2), compare it with `build_payload` in `hwprice/client.py` and fix it. Add a test for the new shape |
| `an unknown spec is rejected` | The endpoint now accepts bad codes | Prices could be wrong. Do not refresh until you understand it |
| `menuInfo` | The catalog URL changed | Look for the new path in the calculator's JavaScript and update `CALCULATOR_API` |
| `catalog` | A product or sample is malformed | Read the message and fix `data/catalog.json` |

After any fix, run the tests and `verify`, then `refresh`.

## Snapshots are history

Never edit a snapshot. Each file in `data/snapshots/` is the answer of one date, and the Git history
of the folder is the history of prices.

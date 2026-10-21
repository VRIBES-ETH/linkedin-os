# linkedin-os

**Know what to post before anyone else does.** A verified-source radar for finance and tech executives, running inside Claude Code.

Every morning `/radar` reads what regulators, central banks, issuers and research houses have actually published in the last 48 hours, filters it by your topics, and hands you three angles with the primary source attached. No trade press, no aggregators, no "I saw this on LinkedIn".

![Radar output for one day](docs/radar-example.png)

## Install

```bash
git clone https://github.com/VRIBES-ETH/linkedin-os.git ~/.claude/plugins/local/linkedin-os
```

Open Claude Code and run `/radar`. That is it. The scanner is plain Python 3 with no dependencies.

Optional: copy `cliente/temas.example.json` to `cliente/temas.json` and edit the keyword lists to narrow the radar to your topics.

## What you get

| Piece | What it does |
| --- | --- |
| `/radar` | Scans the catalogue, writes `estado/radar-YYYY-MM-DD.md`, then proposes up to three angles with fact, primary source, why now, and a suggested format. Tier 2 items are never proposed until the primary source is located. |
| `fuentes/fuentes.json` | **95 verified sources** with tier, category, method and language: SEC, CFTC, OCC, ESMA, DG FISMA, FCA, PRA, FINMA, HKMA, CNMV, CVM, ECB, Fed, BoE, Banco de España, BIS, FSB, IMF, OMFIF, Tether, Circle, Coinbase Institutional, Fireblocks, Securitize, Glassnode, Messari, Galaxy, Kaiko, Coin Metrics, 21Shares, Pantera, a16z crypto, Allium, RWA.xyz, Chainalysis, TRM Labs, McKinsey, BCG, Citi Institute, JPMorgan Kinexys and more. Validated by hand between May and October 2026 for a daily digital-assets briefing. |
| `scripts/radar.py` | Deterministic scanner. 46 RSS feeds plus 20 pages without RSS watched by link diff. Dedupes against what you already saw. Lists the sources that block robots so you can search them by hand. |
| `hooks/` | Two guards that run before Claude writes or executes anything: a Spanish (Spain) copy lint that blocks em dashes, AI tells, missing accents and non-peninsular lexicon; and a Publer delete guard, because the Publer API delete ignores ids and wipes the whole queue. |
| `publer/GOTCHAS.md` | Sixteen hard-won rules about the Publer API, in Spanish. |

## The tier rule

Tier 1 is a regulator, central bank, institution, the company itself or a primary research house: you may link and quote it. Tier 2 is press, wires and aggregators: they exist to discover, never to cite. The radar prints the rule at the top of every run so it is impossible to forget.

## Adding a source

Check the feed responds with dated entries, decide the tier by the rule above (not by prestige), add it with `activo: true` and the date in `nota`. Pull requests that add or fix a source are welcome; see `fuentes/README.md` for the fields and `CONTRIBUTING.md` for the checks.

## Want the full editorial system?

The radar finds. It does not write. The complete system (voice kit built in a guided interview, writing layers with a 14-test anti-AI audit, infographic and carousel rendering, Publer scheduling with confirmation) is a paid install with a two-hour onboarding session. Details at [blockcha-in.com](https://blockcha-in.com).

Scheduling runs on Publer. Sign up at [publer.com/vribes](https://publer.com/vribes) for 10 % off, or add `VRIBES` under Settings, "Referred by".

## Licence

Code under MIT. The source catalogue `fuentes/fuentes.json` under CC BY 4.0: use it anywhere, credit Víctor Ribes.

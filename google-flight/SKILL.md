---
name: google-flight
description: Search Google Flights for prices via a single deterministic HTTP GET request — no browser, no GUI/CSS rendering, no screenshots. Use this before reaching for browser automation (kimi-webbridge, browser-harness) whenever the task is "what does this route cost", not "show me the page" or "book this seat".
---

# google-flight

A minimalist alternative to browser automation for one job: get a flight price fast.

Where `kimi-webbridge` / `browser-harness` drive a real page (open a tab, wait for
render, click through an autocomplete dropdown, scroll a virtualized calendar,
screenshot to verify), this skill sends one HTTP GET to Google Flights' search
endpoint and parses the JSON payload embedded in the returned HTML. No browser
process, no CSS/layout, no screenshots — just a request and a parse. That makes
it both **faster** (~1-3s vs 10s+ for a single browser `navigate`) and
**lighter on RAM** (no Chromium tab at all).

## When to use this vs. a browser tool

| Situation | Use |
|---|---|
| "What's a TPE→MAD round trip cost around these dates?" | **this skill** |
| Need the exact paired return-flight time, not just a price | this skill for the price, then a browser tool to pin down the return leg (see Limitations) |
| Need to actually book / fill in passenger details / pay | browser tool — this skill is read-only |
| The route keeps raising `IndexError`/`TypeError` (see below) | browser tool as fallback |

## Usage

```bash
uv run scripts/search_flights.py --from TPE --to MAD --depart 2026-10-22 --return 2026-10-31 --currency TWD
```

`uv run` reads the PEP 723 header at the top of the script and installs its
pinned dependencies (`fast-flights`, `typing_extensions`) into an ephemeral
env on first run — nothing to `pip install` by hand, nothing to leave
installed afterward. Battery included.

Key flags:

- `--from` / `--to` — IATA airport codes (e.g. `TPE`, `MAD`)
- `--depart YYYY-MM-DD` — required
- `--return YYYY-MM-DD` — omit for one-way
- `--currency` — e.g. `TWD`, `USD` (blank lets Google pick)
- `--max-stops N` — filters client-side (the library's own server-side stop
  filter crashes the parser on some routes, see below — don't pass it upstream)
- `--depart-window "HH:MM-HH:MM"` / `--arrive-window "HH:MM-HH:MM"` — filter
  the outbound leg's clock-time departure/arrival, e.g. `--arrive-window
  "12:00-18:00"` for "must land in the afternoon"
- `--format json|table` — `json` for another agent/script to consume,
  `table` for a human to read
- `--limit N` — cap results (sorted by price ascending)

On success it exits 0 and prints results. On failure (no results, or the
upstream parser choking) it prints a JSON `{"error": ...}` to stderr/stdout
and exits non-zero — check the exit code, don't just check stdout is non-empty.

## Lessons this distills (from manually driving Google Flights in a real browser first)

1. **Long-haul date math is a trap.** A 19-hour TPE→MAD flight departing
   Taipei at 00:30 can land in Madrid the *same calendar day* — Taipei is far
   enough ahead of Madrid that the timezone gain outpaces the flight time. If
   you want "arrives afternoon on date X", don't assume you need to search
   `--depart` one day earlier; search `--depart` on X itself first and check
   the actual `arrive` field the script prints. Verify, don't guess.
2. **Round-trip here means "outbound options + total price", not two paired
   legs.** Google Flights' own UI is two-step: pick an outbound flight, *then*
   it shows you return options for that specific fare. This script's
   `--return` flag reproduces step one only — you get a real round-trip total
   price, but the itinerary printed is the outbound leg; the specific return
   flight isn't resolved. If you need the actual return time pinned down,
   treat this script's price as a first-pass estimate and confirm the return
   leg with a browser tool.
3. **The reverse-engineered parser is fragile.** It decodes an undocumented,
   unstable `tfs` protobuf param and parses embedded JSON that Google can
   reshape at any time. It reliably breaks (`IndexError`/`TypeError` inside
   `fast_flights.parser`) on some multi-stop long-haul itineraries — TPE→MAD
   one-way hits this every time in testing, while TPE→MAD round-trip and
   TPE→NRT one-way both work fine. This script catches those exceptions and
   reports them cleanly instead of crashing; treat a caught error as "fall
   back to a browser tool for this specific query," not as "the route has no
   flights."
4. **Don't trust server-side `max_stops`.** Passing it into the upstream
   query crashes the parser outright on some routes (empirical finding, not
   documented upstream). This script filters stops client-side instead —
   always fetch unfiltered, then narrow down in Python.
5. **Results aren't identical to what you'd see logged into Chrome.**
   Google Flights personalizes by session/cookies/locale/IP. A price and
   itinerary set fetched this way is a fast, real, but *independent* sample —
   don't be surprised if a browser session run seconds later shows a
   different cheapest option. For anything price-sensitive, sample both and
   take the lower bound as your target, not either single number as gospel.

## Files

- `scripts/search_flights.py` — the whole skill. Self-contained (PEP 723
  inline deps), runs via `uv run`.

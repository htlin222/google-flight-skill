# google-flight

[![Build & Release Skill](https://github.com/htlin222/google-flight-skill/actions/workflows/release.yml/badge.svg)](https://github.com/htlin222/google-flight-skill/actions/workflows/release.yml)
[![GitHub Release](https://img.shields.io/github/v/release/htlin222/google-flight-skill?include_prereleases&label=skill%20version)](https://github.com/htlin222/google-flight-skill/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)
[![Skills Protocol](https://img.shields.io/badge/protocol-vercel--labs%2Fskills-blue)](https://github.com/vercel-labs/skills)
[![Compatible Agents](https://img.shields.io/badge/agents-40%2B-green)](https://github.com/vercel-labs/skills#supported-agents)

> Search Google Flights for prices via a single deterministic HTTP GET request — no browser, no GUI/CSS rendering, no screenshots.

## Install

```bash
npx skills add htlin222/google-flight-skill
npx skills add -g htlin222/google-flight-skill        # global
npx skills add htlin222/google-flight-skill --agent claude-code  # specific agent
```

## What it does

Where browser-automation skills (kimi-webbridge, browser-harness) drive a real
page — open a tab, wait for render, click through an autocomplete dropdown,
scroll a virtualized calendar, screenshot to verify — this skill sends one
HTTP GET to Google Flights' search endpoint and parses the JSON payload
embedded in the returned HTML. No browser process, no CSS/layout, no
screenshots. That makes it both faster (~1-3s vs 10s+ for a single browser
`navigate`) and lighter on RAM (no Chromium tab at all).

It's built for one job: **get a flight price fast**. It's read-only — it
can't book a seat or fill in passenger details, and for a specific paired
outbound+return itinerary it only resolves the outbound leg plus a
round-trip total price estimate (see the "Lessons" section in
[`google-flight/SKILL.md`](google-flight/SKILL.md) for why, and for the
timezone-math trap this skill was built to stop repeating).

```bash
uv run google-flight/scripts/search_flights.py \
  --from TPE --to MAD --depart 2026-10-22 --return 2026-10-31 --currency TWD
```

`uv run` reads the script's inline PEP 723 dependency block and installs
everything it needs into an ephemeral environment on first run — nothing to
`pip install` by hand.

## Skill structure

```
google-flight
├── scripts
│   └── search_flights.py
└── SKILL.md
```

## Protocol

This skill follows the [vercel-labs/skills](https://github.com/vercel-labs/skills) protocol.
Each push to `main` triggers a GitHub Action that packages the skill as a `.skill` file
and creates a release tagged with the commit SHA.

## License

MIT — see [LICENSE](LICENSE).

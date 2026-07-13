#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fast-flights>=3.0.2",
#     "typing_extensions>=4.12",
# ]
# ///
"""Deterministic Google Flights search via raw HTTP GET — no browser, no GUI, no CSS.

Run with `uv run search_flights.py ...` — uv installs the pinned deps into an
ephemeral env on first run, nothing to set up by hand.

Built on the `fast-flights` library, which base64/protobuf-encodes the search
into Google Flights' `tfs` URL param and parses the JSON embedded in the
returned HTML. It never launches a browser or renders anything, so it's a lot
faster and lighter than driving a real page.

Known limitations (see SKILL.md for the full story):
  - A single call returns OUTBOUND leg options plus an aggregate round-trip
    price estimate, not a specific paired return-leg time. Google Flights'
    own UI is two-step (pick outbound, then see return options) and this
    library only automates the first step.
  - The parser can raise IndexError/TypeError on itineraries with unusual
    layouts (observed on some 2-stop long-haul routes). This is caught below
    and reported as a clear error rather than a stack trace.
  - Results can differ from what an interactive/logged-in browser session
    shows (Google varies results by session, locale, and IP). Treat prices
    as a fast first-pass estimate, not a quote — verify before booking.
"""

import argparse
import json
import sys
from datetime import datetime


def parse_window(spec):
    if not spec:
        return None
    start, end = spec.split("-")
    return (
        datetime.strptime(start.strip(), "%H:%M").time(),
        datetime.strptime(end.strip(), "%H:%M").time(),
    )


def in_window(t, window):
    if window is None:
        return True
    start, end = window
    return start <= t <= end


class IncompleteLegData(Exception):
    """Raised when Google's payload left a leg's date/time fields as None.

    Observed on some long-haul routes (e.g. TPE-SYD) where fast-flights'
    parser successfully returns a Flights object but one of its legs has
    unresolved timing data. Callers should skip the offending result rather
    than crash the whole run.
    """


def to_time(simple_dt):
    h = simple_dt.time[0] if simple_dt.time else None
    m = simple_dt.time[1] if simple_dt.time and len(simple_dt.time) > 1 else 0
    if h is None:
        raise IncompleteLegData("missing departure/arrival hour")
    return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()


def to_date_str(simple_dt):
    if not simple_dt.date or any(part is None for part in simple_dt.date):
        raise IncompleteLegData("missing date")
    y, mo, d = simple_dt.date
    return f"{y:04d}-{mo:02d}-{d:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="from_airport", required=True, help="IATA origin code, e.g. TPE")
    ap.add_argument("--to", dest="to_airport", required=True, help="IATA destination code, e.g. MAD")
    ap.add_argument("--depart", required=True, help="Outbound date YYYY-MM-DD")
    ap.add_argument("--return", dest="return_date", help="Return date YYYY-MM-DD (omit for one-way)")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--seat", default="economy", choices=["economy", "premium-economy", "business", "first"])
    ap.add_argument("--currency", default="", help="e.g. TWD, USD (blank = let Google decide)")
    ap.add_argument("--max-stops", type=int, help="Filter client-side by number of stops on the outbound leg")
    ap.add_argument("--depart-window", help='Filter outbound departure clock time, e.g. "06:00-12:00"')
    ap.add_argument("--arrive-window", help='Filter outbound arrival clock time, e.g. "12:00-18:00"')
    ap.add_argument("--limit", type=int, default=10, help="Max results to print, sorted by price")
    ap.add_argument("--format", choices=["json", "table"], default="table")
    args = ap.parse_args()

    try:
        import fast_flights as ff
    except ImportError:
        print(
            json.dumps({"error": "fast-flights not installed. Run this file with `uv run search_flights.py ...`."}),
            file=sys.stderr,
        )
        sys.exit(2)

    flights = [ff.FlightQuery(date=args.depart, from_airport=args.from_airport, to_airport=args.to_airport)]
    trip = "one-way"
    if args.return_date:
        flights.append(ff.FlightQuery(date=args.return_date, from_airport=args.to_airport, to_airport=args.from_airport))
        trip = "round-trip"

    filt = ff.create_filter(
        flights=flights,
        seat=args.seat,
        trip=trip,
        passengers=ff.Passengers(adults=args.adults),
        currency=args.currency,
    )

    try:
        result = ff.get_flights(filt)
    except ff.FlightsNotFound:
        print(json.dumps({"error": "no flights found for this query"}))
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps(
                {
                    "error": f"{type(e).__name__}: {e}",
                    "note": (
                        "fast-flights' parser broke on this route's response shape. "
                        "This happens on some multi-stop long-haul itineraries. "
                        "Fall back to a real-browser tool (e.g. kimi-webbridge) for this query."
                    ),
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    depart_window = parse_window(args.depart_window)
    arrive_window = parse_window(args.arrive_window)

    rows = []
    skipped = 0
    for f in result:
        # fast-flights' round-trip response only ever populates the outbound
        # itinerary here (see module docstring) — treat all legs as one leg
        # of travel from --from to --to, in order.
        outbound_legs = f.flights
        if not outbound_legs or outbound_legs[-1].to_airport.code != args.to_airport:
            continue

        try:
            first_dep = to_time(outbound_legs[0].departure)
            last_arr = to_time(outbound_legs[-1].arrival)
            depart_str = f"{to_date_str(outbound_legs[0].departure)} {first_dep}"
            arrive_str = f"{to_date_str(outbound_legs[-1].arrival)} {last_arr}"
        except IncompleteLegData:
            # Google's payload left this one result's timing unresolved.
            # Skip it rather than crash the whole search — see SKILL.md.
            skipped += 1
            continue

        stops = len(outbound_legs) - 1

        if args.max_stops is not None and stops > args.max_stops:
            continue
        if not in_window(first_dep, depart_window):
            continue
        if not in_window(last_arr, arrive_window):
            continue

        rows.append(
            {
                "price": f.price,
                "currency": args.currency or "default",
                "airlines": f.airlines,
                "stops": stops,
                "depart": depart_str,
                "arrive": arrive_str,
                "duration_min": sum(leg.duration for leg in outbound_legs),
                "route": " -> ".join(
                    [outbound_legs[0].from_airport.code] + [leg.to_airport.code for leg in outbound_legs]
                ),
            }
        )

    rows.sort(key=lambda r: r["price"])
    rows = rows[: args.limit]

    if not rows:
        print(
            json.dumps(
                {
                    "error": "no results matched the given filters",
                    "trip": trip,
                    "skipped_incomplete": skipped,
                }
            )
        )
        sys.exit(1)

    if args.format == "json":
        print(json.dumps({"results": rows, "skipped_incomplete": skipped}, ensure_ascii=False, indent=2))
    else:
        widths = [8, 6, 30, 6, 20, 20, 10]
        header = ["PRICE", "STOPS", "AIRLINES", "DUR(m)", "DEPART", "ARRIVE", "ROUTE"]
        print(" | ".join(h.ljust(w) for h, w in zip(header, widths)))
        for r in rows:
            print(
                " | ".join(
                    str(v).ljust(w)
                    for v, w in zip(
                        [
                            r["price"],
                            r["stops"],
                            ",".join(r["airlines"])[:28],
                            r["duration_min"],
                            r["depart"],
                            r["arrive"],
                            r["route"],
                        ],
                        widths,
                    )
                )
            )
        if trip == "round-trip":
            print(
                "\nNote: price is the round-trip total; times above are the OUTBOUND leg only. "
                "This library returns outbound options + total price in one call, mirroring "
                "Google Flights' own two-step UI (pick outbound, then see return options) — "
                "it does not resolve which specific return flight is paired with the total."
            )
        if skipped:
            print(
                f"\n{skipped} result(s) omitted: Google's payload left their timing data "
                "unresolved (seen on some long-haul routes, e.g. TPE-SYD). Not a sign the "
                "route has no flights — just that those specific results couldn't be parsed."
            )


if __name__ == "__main__":
    main()

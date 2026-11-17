#!/usr/bin/env python3
"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Reads one case file per run (schema makefun/twitch-ccu-case/v1): the
category's viewer count up to the end of the release day's first hour, plus
the hourly curves of past big launches ("comparables"). Writes, for each of
hours 2..24, five quantiles (5/25/50/75/95%) of that hour's viewer count.

How it forecasts
---------------
A launch-day curve is mostly a matter of *shape*: how the audience builds
after the first hour as regions unlock and evening arrives. Absolute size
varies wildly between games, but the shape, measured as the ratio of each
hour's viewers to the first hour's, is comparable across launches. So:

1. For every comparable launch, take its release-day hourly viewers and
   divide each hour by its hour-1 viewers, in log space. This gives one
   shape sample per launch per hour.
2. For each forecast hour, the central shape is the median of those log
   ratios across all comparables that have both hours. The median is robust:
   a few launches whose unlock falls late in the UTC day have enormous
   ratios and would wreck a mean.
3. The spread around the median is asymmetric and widens with the square
   root of the hours since hour 1. Launch curves spike upward far more
   than they fall (evening peaks run several times hour 1, while dips
   rarely go below half), so the upward spread is wider than the downward
   one. A symmetric spread either misses the evening peak or pays for an
   absurdly low floor every hour.
4. Multiply by this case's hour-1 print. If a comparable is missing an
   hour, it simply does not vote for that hour; if too few vote at all,
   the hour falls back to a flat median with the same widening spread.

The program is deterministic (no randomness, no clock, no network) and
uses only the Python standard library. It reads every ``*.in`` file in the
input directory and writes one ``<id>.out`` per case.
"""

import json
import math
import os
import sys
from datetime import datetime

# Standard normal quantiles at the forecast levels. The program reads the
# levels from each case file (they are 0.05/0.25/0.5/0.75/0.95 in the
# schema) instead of assuming them, and falls back to the schema's levels
# if a case carries something unexpected.
Z_BY_LEVEL = {0.05: -1.645, 0.25: -0.674, 0.5: 0.0, 0.75: 0.674, 0.95: 1.645}
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)

# Log-spread per sqrt(hour) below the median and above it (see docstring).
SPREAD_DOWN = 0.12
SPREAD_UP = 0.22

MIN_VOTERS = 3          # comparables needed for a shaped hour, else flat
VIEWER_FLOOR = 1.0      # a print below 1 viewer counts as 1
VIEWER_CAP = 1_000_000_000.0


def parse_time(text):
    """Parse an ISO-8601 UTC timestamp into a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_series(comparable):
    """Hourly viewers for a comparable's release day: 24 slots, None if the
    source has no point for that hour."""
    start = parse_time(comparable["day_start"])
    series = [None] * 24
    for point in comparable.get("hourly", []):
        try:
            when = parse_time(point["from"])
            viewers = point["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        slot = int((when - start).total_seconds() // 3600)
        if 0 <= slot < 24 and viewers is not None:
            series[slot] = viewers
    return series


def weighted_quantile(pairs, level):
    """Smallest value whose cumulative weight reaches ``level`` of the total.

    ``pairs`` is a list of (value, weight); the list is sorted here, so the
    result is deterministic for a given input.
    """
    ordered = sorted(pairs)
    total = sum(weight for _, weight in ordered)
    if total <= 0:
        return None
    target = level * total
    running = 0.0
    for value, weight in ordered:
        running += weight
        if running >= target:
            return value
    return ordered[-1][0]


def hour_median_log_ratio(comparables, hour):
    """Median log(v_hour / v_hour1) across comparables, or None."""
    votes = []
    for series in comparables:
        first = series[0]
        later = series[hour - 1]
        if first and first > 0 and later is not None:
            votes.append((math.log(max(later, 1.0) / max(first, 1.0)), 1.0))
    if len(votes) < MIN_VOTERS:
        return None
    return weighted_quantile(votes, 0.5)


def forecast_hour(hour, hour_one_print, comparables, levels):
    """Five quantiles for one hour, as viewer counts."""
    median_log = hour_median_log_ratio(comparables, hour)
    if median_log is None:
        median_log = 0.0
    widen = math.sqrt(hour - 1)
    quantiles = []
    for level in levels:
        z = Z_BY_LEVEL[level]
        spread = SPREAD_DOWN if z < 0 else SPREAD_UP
        value = hour_one_print * math.exp(median_log + z * spread * widen)
        quantiles.append(value)
    # Keep the row valid: finite, in range, non-decreasing.
    cleaned = []
    previous = VIEWER_FLOOR
    for value in quantiles:
        if not math.isfinite(value):
            value = previous
        value = min(max(value, VIEWER_FLOOR), VIEWER_CAP)
        value = max(value, previous)
        cleaned.append(round(value, 2))
        previous = cleaned[-1]
    return cleaned


def hour_one_print(case):
    """The case's hour-1 print, with fallbacks if the known row is missing."""
    known = case.get("known") or []
    for row in known:
        if row.get("hour") == 1 and row.get("viewers") is not None:
            return max(float(row["viewers"]), VIEWER_FLOOR)
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1]
        if last.get("viewers") is not None:
            return max(float(last["viewers"]), VIEWER_FLOOR)
    return VIEWER_FLOOR


def forecast_case(case):
    """Build the whole forecast object for one case."""
    print_one = hour_one_print(case)
    levels = case.get("levels") or LEVELS
    if not all(level in Z_BY_LEVEL for level in levels):
        levels = LEVELS
    comparables = []
    for comparable in case.get("comparables") or []:
        try:
            comparables.append(release_day_series(comparable))
        except (KeyError, TypeError, ValueError):
            continue
    hours = []
    for hour in range(2, 25):
        hours.append({"hour": hour, "q": forecast_hour(hour, print_one, comparables, levels)})
    return {"hours": hours}


def main(argv):
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    if len(argv) > 1:
        input_dir = argv[1]
    if len(argv) > 2:
        output_dir = argv[2]
    os.makedirs(output_dir, exist_ok=True)
    names = sorted(name for name in os.listdir(input_dir) if name.endswith(".in"))
    for name in names:
        case_id = name[:-3]
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as handle:
            case = json.load(handle)
        forecast = forecast_case(case)
        out_path = os.path.join(output_dir, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(forecast, handle, separators=(",", ":"))
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# GTA VI launch-day Twitch forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/chickensohecker/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/chickensohecker/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day (2026-11-19 UTC), from the viewer count recorded up
to the end of the day's first hour. Entry for the make.fun bounty
`gta6-twitch-ccu-forecast-01`.

## Run

```sh
python3 main.py [input_dir] [output_dir]
```

Without arguments it reads `$MAKEFUN_INPUT_DIR` (else `/input`) and writes
to `$MAKEFUN_OUTPUT_DIR` (else `/output`). For each case `<id>.in` it
writes `<id>.out`: `{"hours": [{"hour": 2, "q": [q05, q25, q50, q75,
q95]}, ...]}` for hours 2–24. Standard library only, no network,
deterministic, well under the 8-second limit per case.

## Method

A launch-day curve is mostly a matter of *shape*. Absolute size varies
wildly between games, but the shape — each hour's viewers divided by the
first hour's — is comparable across launches:

1. Every past launch in the case's `comparables` contributes one shape
   sample per hour: `log(viewers_h / viewers_1)` on its release day.
2. Each forecast hour's central shape is the **median** of those log
   ratios across comparables. The median is robust to the few launches
   whose unlock falls late in the UTC day and whose ratios explode.
3. The spread around the median is **asymmetric** and widens with
   `sqrt(hours since hour 1)`: wider upward (0.22) than downward (0.12),
   because launch curves spike up to several times hour 1 in the evening
   but rarely fall below half of it.
4. Multiply by this case's hour-1 print.

Validated on the kit's four practice launches (Marvel's Wolverine, Red
Dead Redemption 2, God of War Ragnarök, Marvel's Spider-Man 2): mean
log-scale pinball loss **0.250**, against the house persistence baseline's
**0.387**. Per case: Wolverine 0.392, RDR2 0.176, Ragnarök 0.196,
Spider-Man 2 0.234.

## License

MIT. See `LICENSE`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=aehdzdy9&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>

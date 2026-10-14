# Bike Share Toronto MCP

An MCP server that helps Bike Share Toronto commuters plan their trips by asking an AI assistant like Claude in plain language.

Existing apps only show how many bikes and docks a station has right now. This project records station data over time and uses it to predict future availability, so an assistant can answer questions like:

> "Will there be a free dock near my office when I arrive at 9am?"

## Status

| Part | Status |
|---|---|
| **Collector**: records live station data every minute | Working |
| **MCP server**: tools for live info, reliability and predictions | Planned |
| **Model**: predicts bike / dock availability | Planned |

## How it works

Nobody publishes historical station availability, so the collector records it from Bike Share Toronto's public [GBFS feed](https://tor.publicbikesystem.net/customer/gbfs/v2/gbfs.json) (v2.3, no API key needed).

| Feed | What it holds | Saved |
|---|---|---|
| `station_status` | Bikes, e-bikes and free docks per station | Every minute, as Parquet |
| `station_information` | Station names, locations, capacity | Once a day, as raw JSON |
| `vehicle_types` | Bike type codes (classic vs e-bike) | Once a day, as raw JSON |

The collector runs 24/7 in Docker on a Raspberry Pi and keeps going if a request fails.

### Data layout

```
data/
├── station_status/
│   └── date=2026-10-14/
│       ├── 20261014T142300Z.parquet   # one file per snapshot
│       └── ...
├── station_information/
│   └── 2026-10-14.json
└── vehicle_types/
    └── 2026-10-14.json
```

- All times and dates are **UTC**.
- `date=` folders let pandas load every day at once and filter by date:
  ```python
  pd.read_parquet("data/station_status", filters=[("date", ">=", "2026-11-01")])
  ```
- Nested fields (`vehicle_types_available`, `vehicle_docks_available`) are stored as JSON text. Use `json.loads` to unpack them.
- `data/` is not committed to git.

## Running the collector

### With Docker (recommended)

Requires Docker with the Compose plugin. From the project root:

```bash
docker compose up -d --build   # build and start in the background
docker compose logs -f         # watch the logs
docker compose down            # stop
```

The container restarts automatically after crashes and reboots, and saves to `./data`.

### Locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd collector
uv run collector.py
```

Stop with `Ctrl+C`.

## Project structure

```
bikeshare-toronto-mcp/
├── collector/       # data collector (Python + Dockerfile)
├── notebooks/       # data exploration and analysis
├── data/            # collected data (git-ignored)
└── compose.yaml     # Docker Compose setup
```

## Roadmap

- [x] Collect station status every minute
- [x] Run in Docker
- [ ] Deploy to Raspberry Pi
- [ ] Merge each day's snapshots into one file
- [ ] Back up data off the Pi
- [ ] MCP server with live station tools
- [ ] Availability prediction model

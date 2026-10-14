"""Bike Share Toronto collector.

Saves a station_status snapshot every minute (Parquet) and the
station_information and vehicle_types feeds once a day (raw JSON).
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATUS_URL = "https://toronto.publicbikesystem.net/customer/gbfs/v2/en/station_status"
DAILY_FEED_URLS = {
    "station_information": "https://toronto.publicbikesystem.net/customer/gbfs/v2/en/station_information",
    "vehicle_types": "https://toronto.publicbikesystem.net/customer/gbfs/v2/en/vehicle_types",
}

# Fixed schema for station_status. Order sets the column order; unknown fields are dropped.
COLUMN_TYPES = {
    "fetched_at": "datetime64[ns, UTC]",
    "last_updated": "datetime64[ns, UTC]",
    "station_id": "string",
    "num_bikes_available": "Int64",
    "num_bikes_disabled": "Int64",
    "num_docks_available": "Int64",
    "num_docks_disabled": "Int64",
    "is_installed": "boolean",
    "is_renting": "boolean",
    "is_returning": "boolean",
    "is_charging_station": "boolean",
    "status": "string",
    "traffic": "string",
    "last_reported": "datetime64[ns, UTC]",
    "vehicle_types_available": "string",
    "vehicle_docks_available": "string",
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collector")


def fetch_feed(url):
    """Download a GBFS feed.

    Args:
        url: The feed's URL.

    Returns:
        The feed as a dict, exactly as the server sent it.

    Raises:
        requests.RequestException: If the request fails, times out,
            or the server returns an error status (4xx/5xx).
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def build_status_df(feed, fetched_at):
    """Turn a station_status feed into a table with fixed columns and types.

    Nested list fields are stored as JSON text, Unix times are converted to
    UTC timestamps, and the columns are forced to match COLUMN_TYPES.

    Args:
        feed: The station_status feed, as returned by fetch_feed.
        fetched_at: UTC datetime when the feed was requested.

    Returns:
        A DataFrame with one row per station.
    """
    df = pd.DataFrame(feed["data"]["stations"])
    for col in ["vehicle_types_available", "vehicle_docks_available"]:
        if col in df:
            df[col] = df[col].apply(json.dumps)
    df["last_reported"] = pd.to_datetime(df["last_reported"], unit="s", utc=True)
    df["last_updated"] = pd.to_datetime(feed["last_updated"], unit="s", utc=True)
    df["fetched_at"] = fetched_at
    df = df.reindex(columns=COLUMN_TYPES.keys())
    df = df.astype(COLUMN_TYPES)
    return df


def save_snapshot(df, fetched_at):
    """Save one station_status snapshot as a Parquet file.

    Writes to data/station_status/date=<YYYY-MM-DD>/<timestamp>.parquet.
    The file is written under a temporary name and then renamed, so a crash
    mid-write never leaves a half-written .parquet file.

    Args:
        df: The snapshot table from build_status_df.
        fetched_at: UTC datetime of the snapshot; sets the folder and file name.

    Returns:
        The Path of the saved file.
    """
    folder = DATA_DIR / "station_status" / f"date={fetched_at:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)

    final_path = folder / f"{fetched_at:%Y%m%dT%H%M%SZ}.parquet"
    tmp_path = folder / f"{fetched_at:%Y%m%dT%H%M%SZ}.parquet.tmp"

    df.to_parquet(tmp_path, index=False)
    tmp_path.rename(final_path)
    return final_path


def collect_station_status_data():
    """Fetch, build and save one station_status snapshot.

    Returns:
        The Path of the saved file.
    """
    fetched_at = datetime.now(timezone.utc)
    feed = fetch_feed(STATUS_URL)
    df = build_status_df(feed, fetched_at)
    return save_snapshot(df, fetched_at)


def save_daily_feed(name, feed, fetched_at):
    """Save a daily feed as raw JSON.

    Writes to data/<name>/<YYYY-MM-DD>.json, replacing any earlier copy from
    the same day. Uses the same temporary-file-then-rename approach as
    save_snapshot.

    Args:
        name: Feed name, also used as the folder name (e.g. "vehicle_types").
        feed: The feed dict, saved whole and unchanged.
        fetched_at: UTC datetime of the fetch; sets the file name.

    Returns:
        The Path of the saved file.
    """
    folder = DATA_DIR / name
    folder.mkdir(parents=True, exist_ok=True)

    final_path = folder / f"{fetched_at:%Y-%m-%d}.json"
    tmp_path = folder / f"{fetched_at:%Y-%m-%d}.json.tmp"

    tmp_path.write_text(json.dumps(feed))
    tmp_path.rename(final_path)
    return final_path


def collect_daily_feeds():
    """Fetch and save every feed in DAILY_FEED_URLS.

    Returns:
        A list of the saved file Paths.
    """
    fetched_at = datetime.now(timezone.utc)
    paths = []
    for name, url in DAILY_FEED_URLS.items():
        feed = fetch_feed(url)
        paths.append(save_daily_feed(name, feed, fetched_at))
    return paths


def main():
    """Run the collector in an infinite loop.

    Saves a station_status snapshot at the start of every minute, and the
    daily feeds on startup and once per UTC day after that. Failures are
    logged and retried on the next minute instead of stopping the loop.
    """
    log.info("Collector starting up")
    last_daily_date = None
    while True:
        try:
            path = collect_station_status_data()
            log.info("Saved %s", path.name)
        except Exception:
            log.exception("Station status collection failed")

        today = datetime.now(timezone.utc).date()
        if today != last_daily_date:
            try:
                paths = collect_daily_feeds()
                last_daily_date = today
                log.info("Saved daily feeds: %s", [f"{p.parent.name}/{p.name}" for p in paths])
            except Exception:
                log.exception("Daily feed collection failed")

        time.sleep(60 - time.time() % 60)


if __name__ == "__main__":
    main()

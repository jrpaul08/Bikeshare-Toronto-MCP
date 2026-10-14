import requests
import pandas as pd
import json
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATUS_URL = "https://toronto.publicbikesystem.net/customer/gbfs/v2/en/station_status"

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


def fetch_feed(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def build_status_df(feed, fetched_at):
    df = pd.DataFrame(feed['data']['stations'])
    for col in ["vehicle_types_available", "vehicle_docks_available"]:
        if col in df:
            df[col] = df[col].apply(json.dumps)
    df['last_reported'] = pd.to_datetime(df['last_reported'], unit='s', utc=True)
    df['last_updated'] = pd.to_datetime(feed['last_updated'], unit='s', utc=True)
    df['fetched_at'] = fetched_at
    df = df.reindex(columns=COLUMN_TYPES.keys())
    df = df.astype(COLUMN_TYPES)
    return df


def save_snapshot(df, fetched_at):
    folder = DATA_DIR / "station_status" / f"date={fetched_at:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)

    final_path = folder / f"{fetched_at:%Y%m%dT%H%M%SZ}.parquet"
    tmp_path = folder / f"{fetched_at:%Y%m%dT%H%M%SZ}.parquet.tmp"

    df.to_parquet(tmp_path, index=False)
    tmp_path.rename(final_path)
    return final_path


if __name__ == "__main__":
    fetched_at = datetime.now(timezone.utc)
    feed = fetch_feed(STATUS_URL)
    df = build_status_df(feed, fetched_at)
    path = save_snapshot(df, fetched_at)
    print("Saved to", path)

    check = pd.read_parquet(path)
    print(check.shape)
    print(check.dtypes)

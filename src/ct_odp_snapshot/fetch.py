"""Pull the whole asset catalog from a Socrata portal.

One call, one snapshot. The discovery API returns every published asset on
the domain -- datasets, charts, maps, stories, files -- with its metadata.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl
from sodapy import Socrata

from ct_odp_snapshot.settings import get_settings


def fetch_catalog(domain: str | None = None) -> pl.DataFrame:
    """Return the raw catalog: one row per asset, payload kept as a struct.

    The shape is `domain`, `scraped_at`, `payload` -- the payload is left
    nested so `flatten.py` owns every decision about what the fields mean.
    """
    settings = get_settings()
    domain = domain or settings.odp_domain
    scraped_at = dt.datetime.now(tz=dt.UTC).isoformat()

    with Socrata(domain, settings.odp_api_key.get_secret_value()) as client:
        payload: list[dict[str, Any]] = client.datasets()

    return (
        pl.from_dicts(payload, strict=False)
        .to_struct("payload")
        .to_frame()
        .with_columns(
            domain=pl.lit(domain),
            scraped_at=pl.lit(scraped_at),
        )
        .select("domain", "scraped_at", "payload")
    )

"""Load and replace: pull the catalog, flatten it, overwrite the app's data.

There is no history and no incremental load on purpose. Every run throws
away yesterday's files and writes today's. The portal is the system of
record; this repo just holds the latest picture of it.

    uv run etl [output-dir]      # default: app/public
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import polars as pl

from ct_odp_snapshot import flatten
from ct_odp_snapshot.fetch import fetch_catalog
from ct_odp_snapshot.settings import get_settings

DEFAULT_OUT = Path("app") / "public"

# Files this ETL owns. Anything else in the output directory is left alone.
OUTPUTS: tuple[str, ...] = ("assets.csv", "tags.csv", "meta.json")


def enrich(assets: pl.DataFrame, stale_days: int) -> pl.DataFrame:
    """Add the freshness and metadata-completeness columns the app reads."""
    now = dt.datetime.now(tz=dt.UTC)

    return assets.with_columns(
        days_since_update=(
            pl.lit(now) - pl.col("data_updated_at")
        ).dt.total_days(),
        has_description=pl.col("description").is_not_null()
        & (pl.col("description").str.strip_chars() != ""),
        has_attribution=pl.col("attribution").is_not_null(),
        has_category=pl.col("category").is_not_null(),
        has_license=pl.col("license").is_not_null(),
        has_contact=pl.col("contact_email").is_not_null(),
    ).with_columns(
        is_stale=pl.col("days_since_update") > stale_days,
        freshness=pl.when(pl.col("days_since_update") <= 30)  # noqa: PLR2004
        .then(pl.lit("last 30 days"))
        .when(pl.col("days_since_update") <= 90)  # noqa: PLR2004
        .then(pl.lit("31-90 days"))
        .when(pl.col("days_since_update") <= 365)  # noqa: PLR2004
        .then(pl.lit("91-365 days"))
        .when(pl.col("days_since_update").is_not_null())
        .then(pl.lit("over a year"))
        .otherwise(pl.lit("never / unknown")),
    )


def slim(assets: pl.DataFrame) -> pl.DataFrame:
    """Drop the columns the app does not display, so the CSV stays small."""
    return assets.select(
        "scraped_at",
        "name",
        "type",
        "category",
        "attribution",
        "owner_name",
        "creator_name",
        "provenance",
        "license",
        "created_at",
        "updated_at",
        "data_updated_at",
        "days_since_update",
        "freshness",
        "is_stale",
        "download_count",
        "page_views_total",
        "page_views_last_month",
        "n_columns",
        "n_tags",
        "has_description",
        "has_attribution",
        "has_category",
        "has_license",
        "has_contact",
        "permalink",
    ).sort("name")


def summarize(assets: pl.DataFrame, domain: str, stale_days: int) -> dict:
    """Headline numbers, computed once here rather than in the browser."""
    datasets = assets.filter(pl.col("type") == "dataset")

    return {
        "domain": domain,
        "scraped_at": str(assets["scraped_at"].max()),
        "stale_days": stale_days,
        "n_assets": assets.height,
        "n_datasets": datasets.height,
        "n_types": assets["type"].n_unique(),
        "n_categories": assets["category"].drop_nulls().n_unique(),
        "n_publishers": assets["owner_name"].drop_nulls().n_unique(),
        "n_attributions": assets["attribution"].drop_nulls().n_unique(),
        "n_stale": int(assets["is_stale"].sum()),
        "n_fresh_30d": int((assets["freshness"] == "last 30 days").sum()),
        "total_page_views": int(assets["page_views_total"].sum()),
        "total_downloads": int(assets["download_count"].sum()),
    }


def run(out_dir: Path = DEFAULT_OUT) -> dict:
    """Fetch, flatten, and replace every file in `out_dir`."""
    settings = get_settings()

    raw = fetch_catalog(settings.odp_domain)
    assets = enrich(flatten.assets(raw), settings.stale_days)
    meta = summarize(assets, settings.odp_domain, settings.stale_days)

    out_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        (out_dir / name).unlink(missing_ok=True)

    slim(assets).write_csv(out_dir / "assets.csv")
    flatten.tags(raw).write_csv(out_dir / "tags.csv")
    (out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    return meta


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    meta = run(out_dir)
    print(f"wrote {', '.join(OUTPUTS)} to {out_dir}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

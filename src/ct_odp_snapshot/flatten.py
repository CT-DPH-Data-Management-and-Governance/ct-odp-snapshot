"""Flatten a Socrata catalog payload into tidy polars frames.

The `/api/catalog` record mixes several entities -- the asset, the users
behind it, its columns, its tags, its custom metadata -- into one deeply
nested blob. This splits it along those seams:

    assets      one row per asset, scalars only
    tags        one row per (asset, domain tag)

Nothing here is agency specific. Every asset on the domain is in scope.
"""

from __future__ import annotations

import polars as pl

_TIMESTAMP_COLUMNS: tuple[str, ...] = (
    "updated_at",
    "created_at",
    "data_updated_at",
)


def base(raw: pl.DataFrame) -> pl.DataFrame:
    """One row per asset with the payload struct opened one level."""
    return raw.select(
        pl.col("scraped_at").str.to_datetime(strict=False, time_zone="UTC"),
        pl.col("payload").struct.unnest(),
    ).with_columns(asset_id=pl.col("resource").struct.field("id"))


def assets(raw: pl.DataFrame) -> pl.DataFrame:
    """The wide, one-row-per-asset frame the app is built on."""
    opened = base(raw)
    resource = pl.col("resource").struct
    metadata = pl.col("metadata").struct
    classification = pl.col("classification").struct

    frame = opened.select(
        "scraped_at",
        "asset_id",
        metadata.field("domain").alias("domain"),
        resource.field("name").alias("name"),
        resource.field("type").alias("type"),
        resource.field("description").alias("description"),
        resource.field("attribution").alias("attribution"),
        resource.field("contact_email").alias("contact_email"),
        classification.field("domain_category").alias("category"),
        metadata.field("license").alias("license"),
        resource.field("provenance").alias("provenance"),
        resource.field("download_count").alias("download_count"),
        resource.field("updatedAt").alias("updated_at"),
        resource.field("createdAt").alias("created_at"),
        resource.field("data_updated_at").alias("data_updated_at"),
        pl.col("permalink"),
        pl.col("owner").struct.field("display_name").alias("owner_name"),
        pl.col("creator").struct.field("display_name").alias("creator_name"),
        resource.field("columns_name").list.len().alias("n_columns"),
        classification.field("domain_tags").list.len().alias("n_tags"),
        resource.field("page_views")
        .struct.field("page_views_total")
        .alias("page_views_total"),
        resource.field("page_views")
        .struct.field("page_views_last_month")
        .alias("page_views_last_month"),
    )

    return frame.with_columns(
        [
            pl.col(column).str.to_datetime(strict=False, time_zone="UTC")
            for column in _TIMESTAMP_COLUMNS
        ]
    )


def tags(raw: pl.DataFrame) -> pl.DataFrame:
    """One row per (asset, domain tag)."""
    return (
        base(raw)
        .select(
            "asset_id",
            pl.col("classification").struct.field("domain_tags").alias("tag"),
        )
        .explode("tag")
        .filter(pl.col("tag").is_not_null() & (pl.col("tag") != ""))
    )

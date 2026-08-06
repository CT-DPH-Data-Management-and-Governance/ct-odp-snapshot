"""What is on data.ct.gov — a daily snapshot of the whole portal.

Reads the CSVs written by `ct_odp_snapshot.etl` from `public/`, which sits
next to this file. `mo.notebook_location()` resolves to a directory when the
notebook runs locally and to the site URL when it runs as WebAssembly, so the
same code works in both places.

Local:  uv run etl && uv run marimo edit app/snapshot.py
"""

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="data.ct.gov snapshot")


@app.cell(hide_code=True)
def _():
    import sys

    import altair as alt
    import marimo as mo
    import pandas as pd

    return alt, mo, pd, sys


@app.cell(hide_code=True)
def _(mo):
    # Chart ink. One hue for magnitude; a warm accent for "this is the
    # problem bar". Both readable on the light and dark notebook surface.
    BLUE = "#2a78d6"
    ORANGE = "#eb6834"

    DATA = mo.notebook_location() / "public"
    return BLUE, DATA, ORANGE


@app.cell(hide_code=True)
def _(DATA, pd, sys):
    def read_csv(name: str, **kwargs):
        """Read one of the ETL's CSVs, locally or over HTTP.

        GitHub Pages serves these with `Content-Encoding: gzip`. The browser
        has already decompressed the body by the time Python sees it, but the
        header survives, so pandas tries to gunzip plain text and raises
        BadGzipFile. `open_url` hands back the decoded text instead.
        """
        source = str(DATA / name)

        if sys.platform == "emscripten":
            from pyodide.http import open_url

            return pd.read_csv(open_url(source), **kwargs)

        return pd.read_csv(source, **kwargs)

    assets = read_csv(
        "assets.csv",
        parse_dates=["scraped_at", "created_at", "updated_at", "data_updated_at"],
    )
    tags = read_csv("tags.csv")

    scraped_at = assets["scraped_at"].max()
    return assets, scraped_at, tags


@app.cell(hide_code=True)
def _(mo, scraped_at):
    mo.md(
        f"""
        # data.ct.gov — portal snapshot

        Every asset published on the domain: what it is, who publishes it,
        how fresh it is, and how complete its metadata is. Rebuilt daily.

        _Catalog read {scraped_at:%B %d, %Y at %H:%M UTC}._
        """
    )
    return


@app.cell(hide_code=True)
def _(assets, mo):
    _stale = int(assets["is_stale"].sum())
    _fresh = int((assets["freshness"] == "last 30 days").sum())

    mo.hstack(
        [
            mo.stat(
                value=f"{len(assets):,}",
                label="Assets",
                caption=f"{assets['type'].nunique()} kinds",
                bordered=True,
            ),
            mo.stat(
                value=f"{int((assets['type'] == 'dataset').sum()):,}",
                label="Datasets",
                caption="the rest are charts, maps, files, stories",
                bordered=True,
            ),
            mo.stat(
                value=f"{assets['owner_name'].nunique():,}",
                label="Publishing accounts",
                caption="own at least one asset",
                bordered=True,
            ),
            mo.stat(
                value=f"{_fresh:,}",
                label="Updated this month",
                caption=f"{_fresh / len(assets):.0%} of the portal",
                bordered=True,
            ),
            mo.stat(
                value=f"{_stale:,}",
                label="Stale",
                caption=f"no data update in a year — {_stale / len(assets):.0%}",
                bordered=True,
            ),
            mo.stat(
                value=f"{assets['page_views_total'].sum() / 1e6:.1f}M",
                label="Page views",
                caption="all time, all assets",
                bordered=True,
            ),
        ],
        justify="start",
        gap=1,
        wrap=True,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## What is out there

        An *asset* is anything with its own page on the portal. Only some of
        them are datasets — the rest are views, charts, maps, and files built
        on top of datasets, or links out to another system.
        """
    )
    return


@app.cell(hide_code=True)
def _(BLUE, alt, assets, mo, pd):
    def bar(frame: pd.DataFrame, field: str, title: str, color: str = BLUE):
        """Horizontal count bar, longest first, labelled at the tip."""
        base = alt.Chart(frame, title=title).encode(
            y=alt.Y(f"{field}:N", sort="-x", title=None),
            x=alt.X("n:Q", title="assets", axis=alt.Axis(grid=True)),
            tooltip=[
                alt.Tooltip(f"{field}:N", title=title),
                alt.Tooltip("n:Q", title="assets", format=","),
            ],
        )
        return (
            base.mark_bar(color=color, cornerRadiusEnd=4, height=14)
            + base.mark_text(align="left", dx=6, fontSize=11, color="#8a8a86").encode(
                text=alt.Text("n:Q", format=",")
            )
        ).properties(
            width="container",
            height=alt.Step(22),
            # Room on the right so the tip labels are not clipped.
            padding={"left": 5, "top": 5, "right": 44, "bottom": 5},
            background="transparent",
        )

    def counts(frame: pd.DataFrame, field: str, top: int | None = None):
        out = (
            frame.groupby(field, dropna=False)
            .size()
            .reset_index(name="n")
            .sort_values("n", ascending=False)
        )
        out[field] = out[field].fillna("(not set)")
        return out.head(top) if top else out

    _by_type = bar(counts(assets, "type"), "type", "Assets by type")
    _by_category = bar(
        counts(assets, "category"), "category", "Assets by portal category"
    )

    mo.hstack([_by_type, _by_category], widths=[1, 1], gap=2)
    return bar, counts


@app.cell(hide_code=True)
def _(bar, counts, mo, tags):
    mo.vstack(
        [
            mo.md("### Most used tags"),
            bar(counts(tags, "tag", top=20), "tag", "Top 20 domain tags"),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Is it being kept up

        Freshness is `data_updated_at` — when the data behind the asset last
        moved, not when someone edited its description. An asset that has not
        moved in a year is either finished, or a pipeline nobody is running.
        """
    )
    return


@app.cell(hide_code=True)
def _(BLUE, ORANGE, alt, assets, mo, pd):
    _order = [
        "last 30 days",
        "31-90 days",
        "91-365 days",
        "over a year",
        "never / unknown",
    ]
    _fresh = (
        assets.groupby("freshness").size().reindex(_order).fillna(0).reset_index(name="n")
    )
    _fresh["share"] = _fresh["n"] / _fresh["n"].sum()
    # The two trailing buckets are the ones that need somebody to look.
    _fresh["cold"] = _fresh["freshness"].isin(["over a year", "never / unknown"])

    _base = alt.Chart(_fresh, title="Assets by age of last data update").encode(
        y=alt.Y("freshness:N", sort=_order, title=None),
        x=alt.X("n:Q", title="assets"),
        tooltip=[
            alt.Tooltip("freshness:N", title="last update"),
            alt.Tooltip("n:Q", title="assets", format=","),
            alt.Tooltip("share:Q", title="share", format=".0%"),
        ],
    )
    _chart = (
        _base.mark_bar(cornerRadiusEnd=4, height=18).encode(
            color=alt.Color(
                "cold:N",
                scale=alt.Scale(domain=[False, True], range=[BLUE, ORANGE]),
                legend=None,
            )
        )
        + _base.mark_text(align="left", dx=6, fontSize=11, color="#8a8a86").encode(
            text=alt.Text("share:Q", format=".0%")
        )
    ).properties(
        width="container",
        height=alt.Step(28),
        padding={"left": 5, "top": 5, "right": 44, "bottom": 5},
        background="transparent",
    )

    mo.vstack(
        [
            _chart,
            mo.md(
                "Orange is the backlog: no data update in over a year, or no "
                "update timestamp at all."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(BLUE, alt, assets, mo, pd):
    _created = (
        assets.assign(year=assets["created_at"].dt.year)
        .groupby("year")
        .size()
        .reset_index(name="n")
        .dropna()
    )

    _chart = (
        alt.Chart(_created, title="Assets published per year")
        .mark_bar(color=BLUE, cornerRadiusEnd=4, size=18)
        .encode(
            x=alt.X("year:O", title=None),
            y=alt.Y("n:Q", title="assets"),
            tooltip=[
                alt.Tooltip("year:O", title="year"),
                alt.Tooltip("n:Q", title="assets", format=","),
            ],
        )
        .properties(width="container", height=220, background="transparent")
    )

    mo.vstack([mo.md("### When it all showed up"), _chart])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Can somebody find it and trust it

        Metadata completeness across the whole portal. A missing contact or a
        missing license does not break the download — it breaks the person who
        has to decide whether they may use the data.
        """
    )
    return


@app.cell(hide_code=True)
def _(BLUE, alt, assets, mo, pd):
    _fields = {
        "has_description": "description",
        "has_attribution": "attribution (source agency)",
        "has_category": "portal category",
        "has_license": "license",
        "has_contact": "contact email",
    }
    _complete = pd.DataFrame(
        {
            "field": list(_fields.values()),
            "filled": [assets[key].sum() for key in _fields],
        }
    )
    _complete["share"] = _complete["filled"] / len(assets)
    _complete["missing"] = len(assets) - _complete["filled"]

    _base = alt.Chart(_complete, title="Share of assets with the field set").encode(
        y=alt.Y("field:N", sort="-x", title=None),
        x=alt.X("share:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
        tooltip=[
            alt.Tooltip("field:N", title="field"),
            alt.Tooltip("share:Q", title="filled", format=".0%"),
            alt.Tooltip("missing:Q", title="assets missing it", format=","),
        ],
    )
    _chart = (
        _base.mark_bar(color=BLUE, cornerRadiusEnd=4, height=16)
        + _base.mark_text(align="left", dx=6, fontSize=11, color="#8a8a86").encode(
            text=alt.Text("share:Q", format=".0%")
        )
    ).properties(
        width="container",
        height=alt.Step(26),
        padding={"left": 5, "top": 5, "right": 44, "bottom": 5},
        background="transparent",
    )

    mo.vstack([_chart])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Who publishes

        The catalog exposes the account that **owns** each asset. That is who
        has actually published, not who holds publisher rights and never used
        them — treat this as the floor.
        """
    )
    return


@app.cell(hide_code=True)
def _(assets, mo, pd):
    _publishers = (
        assets.groupby("owner_name")
        .agg(
            n_assets=("name", "size"),
            n_datasets=("type", lambda column: (column == "dataset").sum()),
            n_stale=("is_stale", "sum"),
            page_views=("page_views_total", "sum"),
            last_data_update=("data_updated_at", "max"),
        )
        .reset_index()
        .sort_values("n_assets", ascending=False)
    )
    _publishers["pct_stale"] = (
        _publishers["n_stale"] / _publishers["n_assets"]
    ).round(2)
    _publishers["last_data_update"] = _publishers["last_data_update"].dt.date

    mo.ui.table(_publishers, page_size=15, selection=None)
    return


@app.cell(hide_code=True)
def _(assets, bar, counts, mo):
    mo.vstack(
        [
            mo.md("### Attribution strings in use"),
            mo.md(
                "The free-text source field. One agency often spells itself "
                "several ways — which is why this is a text box, not a filter."
            ),
            bar(
                counts(assets, "attribution", top=20),
                "attribution",
                "Top 20 attributions",
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## Browse everything

        Filter the whole catalog. Every row links back to the portal.
        """
    )
    return


@app.cell(hide_code=True)
def _(assets, mo):
    search = mo.ui.text(placeholder="name, attribution, owner…", label="Search")
    type_filter = mo.ui.dropdown(
        options=["all", *sorted(assets["type"].dropna().unique())],
        value="all",
        label="Type",
    )
    freshness_filter = mo.ui.dropdown(
        options=["all", *sorted(assets["freshness"].dropna().unique())],
        value="all",
        label="Freshness",
    )
    category_filter = mo.ui.dropdown(
        options=["all", *sorted(assets["category"].dropna().unique())],
        value="all",
        label="Category",
    )

    mo.hstack(
        [search, type_filter, category_filter, freshness_filter],
        justify="start",
        gap=1,
        wrap=True,
    )
    return category_filter, freshness_filter, search, type_filter


@app.cell(hide_code=True)
def _(
    assets,
    category_filter,
    freshness_filter,
    mo,
    search,
    type_filter,
):
    _view = assets
    if type_filter.value != "all":
        _view = _view[_view["type"] == type_filter.value]
    if category_filter.value != "all":
        _view = _view[_view["category"] == category_filter.value]
    if freshness_filter.value != "all":
        _view = _view[_view["freshness"] == freshness_filter.value]
    if search.value:
        _needle = search.value.strip().lower()
        _haystack = (
            _view["name"].fillna("")
            + " "
            + _view["attribution"].fillna("")
            + " "
            + _view["owner_name"].fillna("")
        )
        _view = _view[_haystack.str.lower().str.contains(_needle, regex=False)]

    _table = _view[
        [
            "name",
            "type",
            "category",
            "attribution",
            "owner_name",
            "data_updated_at",
            "freshness",
            "page_views_total",
            "download_count",
            "permalink",
        ]
    ].sort_values("page_views_total", ascending=False)

    mo.vstack(
        [
            mo.md(f"**{len(_table):,}** of {len(assets):,} assets match."),
            mo.ui.table(_table, page_size=15, selection=None),
        ]
    )
    return


@app.cell(hide_code=True)
def _(assets, mo):
    _cold = (
        assets[assets["type"] == "dataset"]
        .sort_values("data_updated_at", ascending=True, na_position="first")
        .head(25)[
            [
                "name",
                "attribution",
                "owner_name",
                "data_updated_at",
                "days_since_update",
                "page_views_total",
                "permalink",
            ]
        ]
    )

    mo.vstack(
        [
            mo.md("### Coldest datasets"),
            mo.md(
                "Oldest `data_updated_at` first. Some of these are finished "
                "products; the rest are pipeline candidates."
            ),
            mo.ui.table(_cold, page_size=10, selection=None),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo, scraped_at):
    mo.md(
        f"""
        ---

        Built from the Socrata discovery API (`/api/catalog`) at
        {scraped_at:%Y-%m-%d %H:%M} UTC. The ETL is load-and-replace: this page
        shows one snapshot, with no history behind it.
        """
    )
    return


if __name__ == "__main__":
    app.run()

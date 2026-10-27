"""Resolve a client's KPI slots into SQL against the shared model.

The report template never names a metric. It asks for "KPI 1" ... "KPI N".
This module works out, for one client:

  1. which metrics it wants   (its kpi_types' templates, plus extra_kpis)
  2. which of those its data can support   (each metric's inputs vs `sends`)
  3. the SQL for each supported metric      (ratios always as sum / sum)

Metrics the client's data cannot support are not silently dropped: they come
back as `Hidden` entries with a reason, so the report can say what is missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAX_SLOTS = 8  # N: how many KPI slots the template supports; change here
WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


@dataclass
class Slot:
    position: int
    key: str
    label: str
    sql: str
    fmt: str
    better: str
    target: float | None


@dataclass
class Hidden:
    key: str
    label: str
    missing: list[str]

    @property
    def reason(self) -> str:
        return f"needs {', '.join(self.missing)}, which this client does not send"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text())


def load_all() -> tuple[dict, dict, dict]:
    return (load_yaml("config/clients.yaml"),
            load_yaml("semantic/metrics.yaml"),
            load_yaml("semantic/kpi_templates.yaml"))


# ---------------------------------------------------------------- catalog

def catalog(metrics: dict) -> dict[str, dict]:
    """Flatten base / ratio / formula into one dict with a `kind` and `requires`."""
    flat = {}
    for key, m in metrics.get("base", {}).items():
        flat[key] = {**m, "kind": "base", "requires": [key]}
    for key, m in metrics.get("ratio", {}).items():
        flat[key] = {**m, "kind": "ratio", "requires": [m["num"], m["den"]]}
    for key, m in metrics.get("formula", {}).items():
        flat[key] = {**m, "kind": "formula"}
    return flat


def base_sql(key: str, metrics: dict, adjustments: dict) -> str:
    """sum(column), scaled by any agreed adjustment for this client."""
    col = metrics["base"][key]["column"]
    mult = adjustments.get(key, 1.0)
    return f"sum({col})" if mult == 1.0 else f"(sum({col}) * {mult})"


def metric_sql(key: str, metrics: dict, adjustments: dict) -> str:
    m = catalog(metrics)[key]
    if m["kind"] == "base":
        return base_sql(key, metrics, adjustments)
    if m["kind"] == "ratio":
        num = base_sql(m["num"], metrics, adjustments)
        den = base_sql(m["den"], metrics, adjustments)
        scale = m.get("scale", 1)
        expr = f"{num} / nullif({den}, 0)"
        return expr if scale == 1 else f"{scale} * {expr}"
    return m["sql"]  # formula: written by hand, inputs declared in `requires`


# ---------------------------------------------------------------- per client

def wanted(client: dict, templates: dict) -> list[str]:
    """The client's templates merged in order, plus extras, without duplicates."""
    keys: list[str] = []
    for t in client.get("kpi_types", []):
        keys += templates[t]
    keys += client.get("extra_kpis", [])
    return list(dict.fromkeys(keys))


def resolve(client_id: str, clients: dict | None = None, metrics: dict | None = None,
            templates: dict | None = None) -> tuple[list[Slot], list[Hidden]]:
    if clients is None or metrics is None or templates is None:
        c0, m0, t0 = load_all()
        clients, metrics, templates = clients or c0, metrics or m0, templates or t0
    c = clients[client_id]
    cat = catalog(metrics)
    sends = set(c.get("sends", []))
    adjustments = c.get("adjustments") or {}
    targets = c.get("targets") or {}
    names = {"conversion": c.get("conversion", "Conversion")}
    labels = c.get("labels") or {}

    slots, hidden = [], []
    for key in wanted(c, templates):
        m = cat[key]
        # The definition is shared; the name is the client's.
        label = labels.get(key) or m["label"].format(**names)
        missing = [r for r in m["requires"] if r not in sends]
        if missing:
            hidden.append(Hidden(key, label, missing))
            continue
        if len(slots) == MAX_SLOTS:
            hidden.append(Hidden(key, label, [f"a free slot (max {MAX_SLOTS})"]))
            continue
        slots.append(Slot(position=len(slots) + 1, key=key, label=label,
                          sql=metric_sql(key, metrics, adjustments),
                          fmt=m["format"], better=m.get("better", "higher"),
                          target=targets.get(key)))
    return slots, hidden


def slots_for(client_id: str, *args) -> list[Slot]:
    return resolve(client_id, *args)[0]


# ---------------------------------------------------------------- checks

def validate(clients: dict, metrics: dict, templates: dict) -> list[str]:
    """Return a list of configuration errors (empty list means valid)."""
    errors = []
    cat = catalog(metrics)
    for key, m in cat.items():
        for r in m["requires"]:
            if r not in metrics.get("base", {}):
                errors.append(f"metric {key}: requires unknown base measure '{r}'")
    for t, keys in templates.items():
        for k in keys:
            if k not in cat:
                errors.append(f"template {t}: unknown metric '{k}'")
    for cid, c in clients.items():
        for t in c.get("kpi_types", []):
            if t not in templates:
                errors.append(f"{cid}: unknown kpi_type '{t}'")
        for k in c.get("extra_kpis", []):
            if k not in cat:
                errors.append(f"{cid}: unknown metric '{k}' in extra_kpis")
        for s in c.get("sends", []):
            if s not in metrics.get("base", {}):
                errors.append(f"{cid}: sends unknown base measure '{s}'")
        if c.get("week_start") not in WEEKDAYS:
            errors.append(f"{cid}: week_start must be one of {WEEKDAYS}")
        if not c.get("kpi_types") and not c.get("extra_kpis"):
            errors.append(f"{cid}: needs at least one kpi_type or extra_kpi")
        for k in (c.get("labels") or {}):
            if k not in cat:
                errors.append(f"{cid}: label set for unknown metric '{k}'")
        for t in (c.get("targets") or {}):
            if t not in cat:
                errors.append(f"{cid}: target set for unknown metric '{t}'")
    return errors


def check_against_data(con, clients: dict, metrics: dict) -> list[str]:
    """Warn when config and data disagree about what a client sends.

    Config says a client sends revenue but every revenue value is NULL? Or the
    data has sessions the config does not use? Both are worth knowing.
    """
    warnings = []
    for cid, c in clients.items():
        sends = set(c.get("sends", []))
        for key, m in metrics["base"].items():
            n = sum(con.execute(
                f"SELECT count({m['column']}) FROM {t} WHERE client = ?",
                [cid]).fetchone()[0]
                for t in ("fact_daily_performance", "fact_weekly_performance"))
            if key in sends and n == 0:
                warnings.append(f"{cid}: config says it sends {key}, but the data has none")
            if key not in sends and n > 0:
                warnings.append(f"{cid}: data has {key}, but config does not list it in sends")
    return warnings


# ---------------------------------------------------------------- queries

def week_expr(week_start: str) -> str:
    """SQL for the first day of the client's reporting week."""
    start = WEEKDAYS.index(week_start)
    return f"(date - CAST((dayofweek(date) - {start} + 7) % 7 AS INTEGER))"


def _cols(slots: list[Slot]) -> str:
    return ",\n    ".join(f'{s.sql} AS "kpi_{s.position}"' for s in slots)


MEASURES = "spend, impressions, sessions, conversions, revenue"


def weekly_facts(client_id: str, clients: dict) -> str:
    """Daily facts rolled up to the client's week, plus weekly-only facts.

    Both sides carry only additive measures, so a UNION ALL followed by the
    slot SQL (sums, and ratios of sums) gives correct weekly numbers. This
    assumes weekly sources use the client's week start; `validate_grain`
    checks that.
    """
    c = clients[client_id]
    return (
        f"SELECT {week_expr(c['week_start'])} AS week_start, channel, {MEASURES}\n"
        f"  FROM fact_daily_performance WHERE client = '{client_id}'\n"
        f"  UNION ALL\n"
        f"  SELECT week_start, channel, {MEASURES}\n"
        f"  FROM fact_weekly_performance WHERE client = '{client_id}'"
    )


def weekly_query(client_id: str, clients: dict, slots: list[Slot]) -> str:
    return (
        f"WITH facts AS (\n  {weekly_facts(client_id, clients)}\n)\n"
        f"SELECT\n    week_start,\n    {_cols(slots)}\n"
        f"FROM facts\nGROUP BY 1\nORDER BY 1"
    )


def channel_query(client_id: str, clients: dict, slots: list[Slot]) -> str:
    return (
        f"WITH facts AS (\n  {weekly_facts(client_id, clients)}\n)\n"
        f"SELECT\n    channel,\n    {_cols(slots)}\n"
        f"FROM facts\nGROUP BY 1\nORDER BY 1"
    )


def validate_grain(con, clients: dict) -> list[str]:
    """Weekly sources must line up with the client's reporting week.

    If a vendor's week runs Monday to Sunday and the client reports Sunday to
    Saturday, no amount of SQL can realign those totals without guessing.
    Better to say so than to quietly mislabel a week.
    """
    errors = []
    for cid, c in clients.items():
        start = WEEKDAYS.index(c["week_start"])
        bad = con.execute(
            "SELECT count(*) FROM fact_weekly_performance "
            "WHERE client = ? AND dayofweek(week_start) <> ?", [cid, start]).fetchone()[0]
        if bad:
            errors.append(f"{cid}: {bad} weekly rows do not start on {c['week_start']}")
    return errors

"""Render the same standard report for every client, driven only by config.

Usage: python report/render.py            # all clients
       python report/render.py brewbox    # one client
Writes reports/<client_id>.md
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semantic.resolve import (channel_query, check_against_data, load_all,  # noqa: E402
                              resolve, validate, validate_grain, weekly_query)

ROOT = Path(__file__).resolve().parents[1]


def fmt(value, spec: str) -> str:
    """Format specs from the catalog: "$,.2f", ".2%", ".2fx" (a multiple), ",.0f"."""
    if value is None:
        return "n/a"
    if spec.startswith("$"):
        return "$" + format(value, spec[1:])
    if spec.endswith("x"):
        return format(value, spec[:-1]) + "x"
    return format(value, spec)


def pacing(value, target, better: str) -> str:
    if target is None or value is None or better == "none":
        return ""
    good = value <= target if better == "lower" else value >= target
    return " ✓" if good else " ✗"


def render(client_id: str, con, clients: dict, metrics: dict, templates: dict) -> str:
    c = clients[client_id]
    slots, hidden = resolve(client_id, clients, metrics, templates)
    header = "| Week starting | " + " | ".join(s.label for s in slots) + " |"
    sep = "|---" * (len(slots) + 1) + "|"
    lines = [f"# {c['name']}", "",
             f"KPI types: {', '.join(c['kpi_types'])}. "
             f"Reporting week starts on {c['week_start'].title()}. "
             f"KPIs come from config, not from this template.", ""]
    if c.get("adjustments"):
        adj = ", ".join(f"{k} x {v}" for k, v in c["adjustments"].items())
        lines += [f"Agreed adjustments applied: {adj}.", ""]
    weekly_only = [r[0] for r in con.execute(
        "SELECT DISTINCT channel FROM fact_weekly_performance WHERE client = ? ORDER BY 1",
        [client_id]).fetchall()]
    if weekly_only:
        lines += [f"Weekly-only sources: {', '.join(weekly_only)}. "
                  f"This report goes no finer than a week.", ""]
    lines += ["## Weekly KPIs", "", header, sep]
    for row in con.execute(weekly_query(client_id, clients, slots)).fetchall():
        cells = [fmt(v, s.fmt) + pacing(v, s.target, s.better) for v, s in zip(row[1:], slots)]
        lines.append(f"| {row[0]} | " + " | ".join(cells) + " |")
    lines += ["", "## By channel (whole period)", "",
              "| Channel | " + " | ".join(s.label for s in slots) + " |", sep]
    for row in con.execute(channel_query(client_id, clients, slots)).fetchall():
        cells = [fmt(v, s.fmt) for v, s in zip(row[1:], slots)]
        lines.append(f"| {row[0]} | " + " | ".join(cells) + " |")
    if hidden:
        lines += ["", "## Not shown", ""]
        lines += [f"- {h.label}: {h.reason}." for h in hidden]
    if any(s.target for s in slots):
        lines += ["", "✓ on target, ✗ off target."]
    return "\n".join(lines) + "\n"


def main() -> None:
    clients, metrics, templates = load_all()
    errors = validate(clients, metrics, templates)
    if errors:
        sys.exit("config errors:\n  " + "\n  ".join(errors))
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
    grain_errors = validate_grain(con, clients)
    if grain_errors:
        sys.exit("grain errors:\n  " + "\n  ".join(grain_errors))
    for w in check_against_data(con, clients, metrics):
        print("warning:", w)
    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    for cid in sys.argv[1:] or list(clients):
        (out_dir / f"{cid}.md").write_text(render(cid, con, clients, metrics, templates))
        print(f"wrote reports/{cid}.md")


if __name__ == "__main__":
    main()

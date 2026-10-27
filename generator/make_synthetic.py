"""Generate synthetic daily campaign data for three fictional clients.

Nothing here comes from a real company. The numbers are random but shaped
like typical audio and social advertising: spend drives impressions, a
fraction of impressions become site sessions, and a fraction of sessions
convert.

Each client sends a different set of measures, the way real clients do.
A measure a client does not send is written as an empty value (NULL), so the
shared model keeps one shape for everyone.

Some sources only deliver weekly totals. Here PulseFit's radio vendor sends
one row per week (week starting Sunday, matching PulseFit's reporting week),
the way radio post-buy reports often arrive. Those rows go to a separate
file at their own grain instead of being spread across days.

Usage: python generator/make_synthetic.py [--days 120] [--seed 7]
Writes data/raw_daily.csv and data/raw_weekly.csv
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

CLIENTS = {
    # client_id: (daily budget by channel, measures the client sends, avg order value)
    "brewbox": ({"podcast": 1800, "streaming_audio": 900, "social": 1200},
                {"spend", "impressions", "sessions", "conversions"}, None),
    "pulsefit": ({"podcast": 1200, "radio": 1500, "social": 2000},
                 {"spend", "impressions", "conversions"}, None),
    "juniper": ({"podcast": 1500, "social": 2500, "streaming_audio": 700},
                {"spend", "impressions", "sessions", "conversions", "revenue"}, 118.0),
}

CPM = {"podcast": 25.0, "radio": 8.0, "streaming_audio": 14.0, "social": 9.0}
SESSION_RATE = {"podcast": 0.004, "radio": 0.0015, "streaming_audio": 0.0025, "social": 0.006}
# (client_id, channel) pairs whose data arrives as weekly totals only.
WEEKLY_SOURCES = {("pulsefit", "radio")}
FIELDS = ["date", "client", "campaign", "channel",
          "spend", "impressions", "sessions", "conversions", "revenue"]


def generate(days: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    start = date(2025, 1, 1)
    rows = []
    for client_id, (budgets, sends, aov) in CLIENTS.items():
        for channel, budget in budgets.items():
            for d in range(days):
                day = start + timedelta(days=d)
                weekend = day.weekday() >= 5
                spend = budget * rng.uniform(0.7, 1.3) * (0.6 if weekend else 1.0)
                impressions = spend / CPM[channel] * 1000
                sessions = impressions * SESSION_RATE[channel] * rng.uniform(0.8, 1.2)
                conversions = sessions * rng.uniform(0.03, 0.09)
                revenue = conversions * (aov or 0) * rng.uniform(0.85, 1.15)
                values = {
                    "spend": round(spend, 2),
                    "impressions": int(impressions),
                    "sessions": int(sessions),
                    "conversions": int(conversions),
                    "revenue": round(revenue, 2),
                }
                rows.append({
                    "date": day.isoformat(),
                    "client": client_id,
                    "campaign": f"{client_id}_{channel}",
                    "channel": channel,
                    # What the client does not send stays empty.
                    **{k: (v if k in sends else "") for k, v in values.items()},
                })
    return rows


def split_weekly(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Move weekly-only sources out of the daily rows, summed to Sunday weeks."""
    daily, weekly = [], {}
    for r in rows:
        if (r["client"], r["channel"]) not in WEEKLY_SOURCES:
            daily.append(r)
            continue
        d = date.fromisoformat(r["date"])
        week = d - timedelta(days=(d.weekday() + 1) % 7)  # back to Sunday
        key = (week.isoformat(), r["client"], r["campaign"], r["channel"])
        acc = weekly.setdefault(key, {"week_start": key[0], "client": key[1],
                                      "campaign": key[2], "channel": key[3]})
        for m in ("spend", "impressions", "sessions", "conversions", "revenue"):
            if r[m] == "":
                acc.setdefault(m, "")
            else:
                acc[m] = round(acc.get(m, 0) + r[m], 2)
    return daily, list(weekly.values())


def write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    daily, weekly = split_weekly(generate(args.days, args.seed))
    out = Path(__file__).resolve().parents[1] / "data"
    out.mkdir(exist_ok=True)
    write(out / "raw_daily.csv", daily, FIELDS)
    write(out / "raw_weekly.csv", weekly, ["week_start"] + FIELDS[1:])


if __name__ == "__main__":
    main()

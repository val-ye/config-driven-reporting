"""Load the synthetic CSV into a local DuckDB warehouse and build the model."""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def build(db_path: Path = ROOT / "data" / "warehouse.duckdb") -> Path:
    con = duckdb.connect(str(db_path))
    for name in ("raw_daily", "raw_weekly"):
        raw = ROOT / "data" / f"{name}.csv"
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv_auto('{raw}')")
    con.execute((ROOT / "model" / "schema.sql").read_text())
    n_d = con.execute("SELECT count(*) FROM fact_daily_performance").fetchone()[0]
    n_w = con.execute("SELECT count(*) FROM fact_weekly_performance").fetchone()[0]
    con.close()
    print(f"built {db_path.name}: {n_d} daily and {n_w} weekly fact rows")
    return db_path


if __name__ == "__main__":
    build()

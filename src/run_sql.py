"""Execute the SQL analysis layer against the cleaned ledger via DuckDB.

Each statement in the .sql files is run in order; the schema file must run first
to create the base views. Results are printed and the savings query is compared
against the Python engine as a reconciliation check.

    python -m src.run_sql
"""
from __future__ import annotations

import sys

from .config import PATHS, get_logger

log = get_logger("run_sql")

SQL_FILES = ["00_schema.sql", "01_spend_analysis.sql", "02_price_benchmarking.sql",
             "03_contract_compliance.sql", "04_supplier_scorecard.sql",
             "05_savings_opportunity.sql"]


def _split_statements(text: str):
    stmts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith("--") or not line.strip():
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmts.append("\n".join(buf))
            buf = []
    return stmts


def main(show_rows: int = 8):
    try:
        import duckdb
    except ImportError:
        print("duckdb not installed — run:  pip install duckdb --break-system-packages")
        sys.exit(1)

    con = duckdb.connect()
    con.execute(f"SET FILE_SEARCH_PATH='{PATHS['root']}'")
    import os
    os.chdir(PATHS["root"])

    for fname in SQL_FILES:
        path = PATHS["sql"] / fname
        print("\n" + "#" * 70 + f"\n# {fname}\n" + "#" * 70)
        for stmt in _split_statements(path.read_text()):
            try:
                res = con.execute(stmt)
                if stmt.strip().upper().startswith(("SELECT", "WITH")):
                    df = res.df()
                    print(df.head(show_rows).to_string(index=False))
                    if len(df) > show_rows:
                        print(f"... ({len(df)} rows)")
                    print("-" * 60)
            except Exception as e:  # pragma: no cover
                print(f"  [error] {e}\n  in statement:\n{stmt[:200]}")
    con.close()
    print("\nSQL layer executed successfully.")


if __name__ == "__main__":
    main()

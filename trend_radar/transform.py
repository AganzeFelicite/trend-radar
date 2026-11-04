"""Transform layer: dbt build (seeds, models, tests) then dbt source freshness, logged in connector_runs.

status: ok · partial (a warn-level test or a stale source) · error (a model or blocking test failed; downstream is skipped).
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from trend_radar.db import connector_run

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"
BAD = {"error", "fail", "runtime error"}


def _dbt(*args: str) -> tuple[subprocess.CompletedProcess, list[dict]]:
    # target/ and logs/ go to /tmp: the app directory is read-only for the container's non-root user.
    target = os.environ.get("DBT_TARGET_PATH") or os.path.join(tempfile.gettempdir(), "dbt", "target")
    env = {**os.environ, "DBT_TARGET_PATH": target,
           "DBT_LOG_PATH": os.environ.get("DBT_LOG_PATH") or os.path.join(tempfile.gettempdir(), "dbt", "logs")}
    results_file = Path(target) / ("sources.json" if args[0] == "source" else "run_results.json")
    results_file.unlink(missing_ok=True)  # never read a stale file from a previous run
    p = subprocess.run(["dbt", *args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)],
                       env=env, capture_output=True, text=True)
    results = json.loads(results_file.read_text())["results"] if results_file.exists() else []
    return p, results


def _name(r: dict) -> str:
    # model/seed/test.<package>.<name>[.<hash>]  ·  source.<package>.<source>.<table>
    parts = r["unique_id"].split(".")
    return parts[3] if parts[0] == "source" else parts[2]


def build() -> None:
    with connector_run("dbt", "build") as (s, run):
        p, results = _dbt("build")
        run.items_count = sum(r["status"] in ("success", "pass") for r in results)
        failed = [f"{_name(r)}: {r['status']}" for r in results if r["status"] in BAD]
        if failed or p.returncode != 0:  # no results at all = dbt itself failed (connection, compile)
            raise RuntimeError("; ".join(failed) or p.stdout[-1500:])
        notes = [f"{_name(r)}: warn {r.get('failures')}" for r in results if r["status"] == "warn"]

        _, fresh = _dbt("source", "freshness")
        notes += [f"stale {_name(r)}: {r['status']}" for r in fresh if r["status"] != "pass"]
        if notes:
            run.status, run.error = "partial", "; ".join(notes)[:2000]

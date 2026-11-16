"""How long do the dashboard's reads wait while the loader reloads? (docs/evidence/v3_reload_lock.txt)

The loader's one transaction takes ACCESS EXCLUSIVE on labels and drugs (DROP INDEX, TRUNCATE) and
keeps it until its one commit; a SELECT needs ACCESS SHARE, so it waits. Measured, not designed away.
Two sessions:
  - the probe, inside the app container (the dashboard's own image, network and settings): every
    0.5 s a new connection runs drugs_for_condition('migraine', 'all') and prints when it started and
    how long it took (a query that waits delays the next one: one reader, like one dashboard user);
  - this script, on the host: starts the probe, after 5 s runs `docker compose run --rm loader`
    (the default 100%, the extract), then reads the loader's step times from pipeline_timings.
Run from the repo root with the stack up at 100%:  python3 docs/evidence/v3_reload_lock.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

PROJECT, PROBE_S = "de-v3", 45
RUN_ID = f"v3-reload-lock-{int(time.time())}"   # one id per run: pipeline_timings keeps every run
COMPOSE = ["docker", "compose", "-p", PROJECT]


def probe(seconds):
    """Inside the app container (sys.argv: - probe <seconds>)."""
    import psycopg
    from pathlib import Path
    text = Path("/app/sql/queries.sql").read_text(encoding="utf-8")
    sql = text.split("-- name: drugs_for_condition\n")[1].split("-- name:")[0].strip().rstrip(";")
    db = dict(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), dbname=os.environ["POSTGRES_DB"],
              user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"])
    end, nxt = time.time() + seconds, time.time()
    while time.time() < end:
        time.sleep(max(0.0, nxt - time.time()))
        start = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        with psycopg.connect(**db, connect_timeout=5) as conn:   # a new connection, as each dashboard run
            n = len(conn.execute(sql, {"condition": "migraine", "product_type": "all"}).fetchall())
        print(f"{start.isoformat()} {1000 * (time.perf_counter() - t0):.1f} {n}", flush=True)
        nxt += 0.5


def ts(text):
    """'2026-11-05 20:10:00.123456+00' (psql) or an isoformat string -> epoch seconds."""
    text = text.replace(" ", "T")
    return datetime.fromisoformat(text + ":00" if text.endswith("+00") else text).timestamp()


def main():
    with open(__file__, encoding="utf-8") as me:
        prober = subprocess.Popen(COMPOSE + ["exec", "-T", "app", "python", "-", "probe", str(PROBE_S)],
                                  stdin=me, stdout=subprocess.PIPE, text=True)
    time.sleep(5)
    t_run = time.time()
    loader = subprocess.run(COMPOSE + ["run", "--rm", "-e", f"RUN_ID={RUN_ID}", "loader"], capture_output=True, text=True)
    t_done = time.time()
    out, _ = prober.communicate()
    print(f"$ docker compose -p {PROJECT} run --rm -e RUN_ID={RUN_ID} loader   (started "
          f"{datetime.fromtimestamp(t_run, timezone.utc).strftime('%H:%M:%S.%f')[:-3]} UTC, exit code {loader.returncode}, "
          f"wall time {t_done - t_run:.1f} s; loader lines with a step time)")
    for line in loader.stdout.splitlines():
        if line.rstrip().endswith(" s") or "rows loaded" in line:
            print("  " + line)
    rows = subprocess.run(COMPOSE + ["exec", "-T", "db", "psql", "-U", "team", "-d", "drugs", "-AtF", "|", "-c",
                          f"SELECT step, started_at, finished_at FROM pipeline_timings WHERE run_id = '{RUN_ID}'"],
                          capture_output=True, text=True, check=True).stdout.split("\n")
    steps = {s: (ts(a), ts(b)) for s, a, b in (r.split("|") for r in rows if r)}
    lock_from, lock_to = steps["schema_and_truncate"][0], steps["commit"][1]
    print(f"\nlock window (pipeline_timings): schema_and_truncate started "
          f"{datetime.fromtimestamp(lock_from, timezone.utc).strftime('%H:%M:%S.%f')[:-3]}, commit finished "
          f"{datetime.fromtimestamp(lock_to, timezone.utc).strftime('%H:%M:%S.%f')[:-3]} UTC: {lock_to - lock_from:.3f} s")
    print("\nprobe: started (UTC) | ms | rows | relation to the lock window")
    probes = []
    for line in out.splitlines():
        start, ms, n = line.split()
        t, ms = ts(start), float(ms)
        where = ("before" if t + ms / 1000 < lock_from else "after" if t > lock_to
                 else "started in the window" if t >= lock_from else "overlaps the start")
        probes.append((t, ms, int(n), where))
        print(f"  {start[11:23]} | {ms:9.1f} | {n:>2} | {where}")
    normal = sorted(ms for _, ms, _, w in probes if w in ("before", "after"))
    # the window ends when the loader's client sees its commit return; the server releases the lock a
    # little earlier, so the last reads "in the window" may not wait: count only reads over 1 s
    waited = [p for p in probes if p[3] != "before" and p[3] != "after" and p[1] > 1000]
    print(f"\nqueries outside the window: {len(normal)}, median {normal[len(normal) // 2]:.1f} ms, max {normal[-1]:.1f} ms")
    if waited:
        t, ms, _, _ = waited[0]
        print(f"reads that waited (over 1 s): {len(waited)}; the first started {t - lock_from:.3f} s after the window "
              f"opened and took {ms / 1000:.3f} s; it returned {t + ms / 1000 - lock_to:+.3f} s from the end of the commit step")
        print(f"longest read: {max(ms for _, ms, _, _ in probes) / 1000:.3f} s; rows of every query: "
              f"{sorted({n for _, _, n, _ in probes})}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["probe"]:
        probe(float(sys.argv[2]))
    else:
        main()

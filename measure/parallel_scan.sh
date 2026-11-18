#!/bin/bash
# Parallel-scan experiment at 100%: one fresh load (v2 defaults, extract cache on), then
# measure/parallel_scan.py in the loader image. Run from the repository root:
#     bash measure/parallel_scan.sh > measure/results_experiments/parallel_scan/run.txt
set -eu
P="docker compose -p ${PROJECT:-de-exp}"
echo "# $(date -u '+%Y-%m-%d %H:%M:%S') UTC, $(git rev-parse --short HEAD), project ${PROJECT:-de-exp}, load average: $(cut -d' ' -f1-3 /proc/loadavg)"
$P down -v >/dev/null 2>&1
$P up -d db >/dev/null 2>&1
until $P exec -T db sh -c 'pg_isready -q -U $POSTGRES_USER -d $POSTGRES_DB' 2>/dev/null; do sleep 1; done
SAMPLE_FRACTION=1.0 RUN_ID=parallel-scan-100 EXTRACT_CACHE=1 $P run --rm --no-deps loader 2>&1 | grep -E "rows loaded|ANSWER"
$P run --rm --no-deps -v ./measure:/measure loader python /measure/parallel_scan.py 2>&1
$P down -v >/dev/null 2>&1
echo "# done $(date -u '+%Y-%m-%d %H:%M:%S') UTC"

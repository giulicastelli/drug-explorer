#!/bin/bash
# GIN expression-index experiment: stored GENERATED tsv column + GIN on it (A, v2) against
# NO stored column + a GIN index on the expression to_tsvector('english', indications) (B).
# ONE change, through the loader's switch TSV_MODE:
#   A = generated   (sql/schema.sql and sql/indexes.sql as they are)
#   B = expression  (the loader drops tsv before COPY and builds the index on the expression)
# 25% and 100%, 3 loads in each state, in the order A B B A A B, a fresh volume for every load,
# extract cache on (the rows come from data/clean, so the zips are not parsed again).
# After each load, measure/gin_expression_queries.py reads the disk sizes, times the migraine query
# (1 warm-up + 3 timed) and saves its EXPLAIN (ANALYZE, BUFFERS). Run from the repository root:
#     bash measure/gin_expression.sh > measure/results_experiments/gin_expression/runs.txt
set -eu
P="docker compose -p ${PROJECT:-de-exp}"
q() { $P exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -At -c \"$1\""; }
step() { q "SELECT round(seconds::numeric, 3) FROM pipeline_timings WHERE run_id = '$1' AND step = '$2'"; }
echo "# $(date -u '+%Y-%m-%d %H:%M:%S') UTC, $(git rev-parse --short HEAD), project ${PROJECT:-de-exp}, load average: $(cut -d' ' -f1-3 /proc/loadavg)"
for size in 0.25 1.0; do
  n=0
  for mode in generated expression expression generated generated expression; do
    n=$((n + 1))
    run_id="gin-$mode-$size-$n"
    $P down -v >/dev/null 2>&1                    # fresh volume: equal conditions for every load
    $P up -d db >/dev/null 2>&1
    until $P exec -T db sh -c 'pg_isready -q -U $POSTGRES_USER -d $POSTGRES_DB' 2>/dev/null; do sleep 1; done
    echo "# load $n: size=$size mode=$mode run_id=$run_id load average: $(cut -d' ' -f1-3 /proc/loadavg)"
    t0=$(date +%s.%N)
    SAMPLE_FRACTION=$size TSV_MODE=$mode RUN_ID=$run_id EXTRACT_CACHE=1 $P run --rm --no-deps loader >/dev/null 2>&1
    t1=$(date +%s.%N)
    echo "ROW,$size,$mode,$n,loader_wall,$(echo "$t1 - $t0" | bc),s,docker compose run loader (container start included)"
    for s in read_extract copy index_build build_drugs analyze pipeline_total; do
      echo "ROW,$size,$mode,$n,$s,$(step "$run_id" "$s"),s,pipeline_timings"
    done
    echo "ROW,$size,$mode,$n,load_path,$(q "SELECT value FROM load_info WHERE key = 'load_path'"),text,load_info"
    # the query side: every line it prints starting with ROW, gets the size, mode and load number
    TSV_MODE=$mode $P run --rm --no-deps -v ./measure:/measure loader python /measure/gin_expression_queries.py 2>&1 \
      | sed "s/^ROW,/ROW,$size,$mode,$n,/"
  done
done
$P down -v >/dev/null 2>&1
echo "# done $(date -u '+%Y-%m-%d %H:%M:%S') UTC"

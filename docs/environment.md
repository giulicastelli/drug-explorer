# Environment (facts only, every line from a command)

## Our laptop (18 Nov 2026)

The laptop where `measure/results_laptop/` was measured. The commands ran on 18 Nov 2026 at 17:34 UTC. They are the commands of the cloud VM run; macOS has no `lscpu`, `nproc`, `free` or `/etc/os-release`, so those are replaced by `sysctl` and `sw_vers`, and `uname -a` by `uname -srm` (without the computer's name). Output pasted as it came.

```
$ sysctl -n machdep.cpu.brand_string
Apple M4
```
```
$ sysctl hw.ncpu hw.physicalcpu hw.logicalcpu hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu
hw.ncpu: 10
hw.physicalcpu: 10
hw.logicalcpu: 10
hw.perflevel0.physicalcpu: 4
hw.perflevel1.physicalcpu: 6
```
```
$ sysctl -n hw.logicalcpu
10
```
```
$ sysctl -n hw.memsize
17179869184
```
```
$ df -h /
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   228Gi    13Gi    49Gi    21%    484k  515M    0%   /
```
```
$ uname -srm
Darwin 27.0.0 arm64
```
```
$ sw_vers
ProductName:		macOS
ProductVersion:		27.0.1
BuildVersion:		26A434
```
```
$ docker --version
Docker version 29.8.2, build 7fc2dff
```
```
$ docker compose version
Docker Compose version v5.5.1
```
```
$ docker info --format '{{.ServerVersion}} {{.Driver}} cgroup v{{.CgroupVersion}} {{.NCPU}} CPUs {{.MemTotal}} bytes'
29.8.2 overlayfs cgroup v2 10 CPUs 8319504384 bytes
```
```
$ git --version
git version 2.54.0 (Apple Git-157)
```
```
$ python3 --version
Python 3.14.7
```
```
$ docker image ls --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep -E '^(postgres:16|python:3.12-slim) '
python:3.12-slim 05cda9777409 205MB
postgres:16 ca0bd484cb98 663MB
```
```
$ docker run --rm postgres:16 postgres --version
postgres (PostgreSQL) 16.15 (Debian 16.15-1.pgdg13+2)
```
```
$ uptime
18:34  up 17 days,  7:05, 2 users, load averages: 2.95 3.38 2.82
```

## Docker on the cloud VM

Benchmarks v1, v2 and v3 ran on a cloud VM (4 vCPU Intel Xeon @ 2.80 GHz, 15.7 GiB RAM, Ubuntu 24.04.5, `measure/README.md`). Its command output of 5 Nov 2026 is in the git history of this file. The notes below are about that VM.

1. The Docker daemon was running when this project started (its `docker info` answered on 5 Nov). In the template build earlier the same day it had to be started by hand (template `docs/environment.md`, item 1).
2. **No image is pulled from Docker Hub.** Anonymous pulls from `registry-1.docker.io` were refused with `429 Too Many Requests` earlier the same day (template D-3). The two base images already on the machine are used: `postgres:16` (pulled from Google's Docker Hub mirror and tagged with its usual name, template D-3) and `python:3.12-slim`.
3. **`python:3.12-slim` here is a VM-only variant**: the official image plus the VM proxy's CA bundle, so that `pip install` inside a build can verify TLS (template `docs/environment.md`, "TLS inside containers", and D-4). It is not rebuilt, re-tagged or removed by this project. The repository's Dockerfiles name the plain official image, which is what a laptop uses. Effect on measurements: none expected on time, memory or database size (Judgement, as in template D-4).
4. `docker stats --no-stream` works (cgroup v1), so memory is measured per container with the course's tool. On cgroup v1, what `docker stats` counts as a container's memory includes part of the file cache; this matters for the `db` line (`measure/predictions.md` P30).
5. **The machine is shared.** Other jobs run Docker on it at the same time (for example a README test of the template, compose project `lombardy-temperature`, port 8501). This project uses only its own compose project names (`-p de-...`) and its own `APP_PORT`, and never prunes or removes other projects' containers, volumes or images. At the `uptime` above, no container was running. The benchmark records the load average before each run.

## Network checks (5 Nov 2026)

- `https://api.fda.gov/download.json` and `https://download.open.fda.gov/drug/label/...`: reachable; the research step downloaded the 14 label zips (1,858,907,416 bytes in 85.7 s, research `REPORT.md` 1), and the loader's own download path fetched the manifest and partition 14 in 1.12 s (D-7).
- `https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip`: `curl` → HTTP 200, 27,689,578 bytes in 1.8 s (for `docs/dataset_decision.md`).
- PyPI: reachable through the proxy from inside `docker build` (the core images installed `psycopg[binary]==3.3.6`, `ijson==3.6.0`, `streamlit==1.66.0`).

## Host-side tools used for the documents

- Mermaid CLI `mmdc` 11.17.1 for `docs/architecture.png` and `.svg`.
- A Python venv with ijson (outside the repository), used only to read labels by hand.

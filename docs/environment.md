# Environment (facts only, every line from a command run on 5 Nov 2026)

The same commands as the template's `docs/environment.md`, run again on this machine at about 14:56 UTC. Output pasted as it came.

```
$ lscpu | grep -E 'Model name|^CPU\(s\)|Thread|Core|Socket|'
CPU(s):                                  4
Model name:                              Intel(R) Xeon(R) Processor @ 2.80GHz
Thread(s) per core:                      1
Core(s) per socket:                      4
Socket(s):                               1
 cache: 33 MiB (1 instance)
```
```
$ nproc
4
```
```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            15Gi       787Mi        12Gi        29Mi       2.7Gi        14Gi
Swap:             0B          0B          0B
```
```
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda        252G   18G   21G  47% /
```
```
$ uname -a
Linux vm 6.18.44-fc-v236 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
```
```
$ cat /etc/os-release | head -2
PRETTY_NAME="Ubuntu 24.04.5 LTS"
NAME="Ubuntu"
```
```
$ docker --version
Docker version 29.9.2, build a82e528
```
```
$ docker compose version
Docker Compose version v5.6.1
```
```
$ docker info --format '{{.ServerVersion}} {{.Driver}} cgroup v{{.CgroupVersion}} {{.NCPU}} CPUs {{.MemTotal}} bytes'
29.9.2 overlayfs cgroup v1 4 CPUs 16867418112 bytes
```
```
$ git --version
git version 2.43.0
```
```
$ python3 --version
Python 3.13.18
```
```
$ docker image ls --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep -E '^(postgres:16|python:3.12-slim) '
python:3.12-slim d847d0ccfab8 178MB
postgres:16 5db6dac2ef5d 642MB
```
```
$ docker run --rm postgres:16 postgres --version
postgres (PostgreSQL) 16.15 (Debian 16.15-1.pgdg13+2)
```
```
$ uptime
 14:56:06 up  5:18,  0 user,  load average: 0.38, 1.16, 1.07
```

## Docker on the cloud VM

1. The Docker daemon was running when this project started (`docker info` above answers). In the template build earlier the same day it had to be started by hand (template `docs/environment.md`, item 1).
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

# kegbot-pycore — Claude Code context

## What this is
Python daemon that bridges a Kegboard Arduino device to the Kegbot server via Redis.
Two long-running processes built from this repo:
- **kegboard daemon** (`bin/kegboard_daemon.py`) — reads serial messages from the Arduino and publishes flow/temperature events to Redis
- **pycore** (`bin/kegbot_core.py`) — consumes those events and drives the kegbot server API

## Development workflow
Code is written on the **MacBook** (`/Users/frodelangelo/src/kegbot-pycore`), then built and deployed on the **Pi** (`frode@kegberry`).

```
# 1. Make changes locally, commit, push
git add <files> && git commit -m "..." && git push

# 2. SSH to Pi, pull, build
ssh kegberry "cd ~/src/kegbot-pycore && git pull && docker build -t kegbot/pycore:latest ."

# 3. Deploy (docker-compose lives in ~/kegberry on the Pi)
ssh kegberry "cd ~/kegberry && docker compose up -d kegboard"
# or to restart both services:
ssh kegberry "cd ~/kegberry && docker compose up -d kegboard pycore"

# 4. Check logs
ssh kegberry "docker logs kegberry-kegboard-1 --tail 50"
ssh kegberry "docker logs kegberry-pycore-1 --tail 50"
```

## Pi directory layout
| Path | Purpose |
|------|---------|
| `~/src/kegbot-pycore` | this repo |
| `~/src/kegbot-server` | kegbot Django server |
| `~/src/kegboard` | Arduino firmware + kegboard Python library |
| `~/kegberry/` | docker-compose deployment (docker-compose.yml, nginx.conf, data/) |

## Docker containers (docker-compose project: kegberry)
| Container | Image | Role |
|-----------|-------|------|
| `kegberry-kegboard-1` | `kegbot/pycore:latest` | kegboard serial daemon |
| `kegberry-pycore-1` | `kegbot/pycore:latest` | pycore event processor |
| `kegberry-kegnet-listener-1` | `ghcr.io/flangelo/kegbot-server:latest` | kegnet Redis listener |
| `kegberry-kegbot-1` | `ghcr.io/flangelo/kegbot-server:latest` | Django app |
| `kegberry-workers-1` | `ghcr.io/flangelo/kegbot-server:latest` | RQ background workers |
| `kegberry-nginx-1` | `nginx:alpine` | reverse proxy (port 8000) |
| `kegberry-redis-1` | `redis:7.2` | message bus + task queue |
| `kegberry-mysql-1` | `mariadb:10.11` | database |

## Known build constraints
- **Base image must be `python:3.11-alpine`** — Python 3.12 removed the `imp` module, which the `future` package (and other kegbot deps) still use. 3.11 retains it; 3.11 is supported until 2027.
- **Pin `pipenv<2024`** — pipenv 2024+ rejects `python_version = "3"` (the spec in Pipfile/Pipfile.lock) as ambiguous in `--deploy` mode. Older pipenv accepts it.

## Known runtime issue (fixed)
`kegboard_daemon.py` used to crash with `ValueError: Bad length, must be exactly 4 bytes` during high-frequency flow pulse bursts (serial framing corruption). Fixed by catching `ValueError` in `service_devices()` — the daemon now logs a warning and continues rather than aborting.

## Useful debugging
```bash
# Watch kegboard live
ssh kegberry "docker logs -f kegberry-kegboard-1"

# Check all container health
ssh kegberry "docker ps"

# Rebuild without cache (if packages seem stale)
ssh kegberry "cd ~/src/kegbot-pycore && docker build --no-cache -t kegbot/pycore:latest ."
```

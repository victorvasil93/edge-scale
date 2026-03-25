# EdgeScale

Ingestion and processing pipeline for edge device telemetry. gRPC in, Redis Streams for queuing, async Python workers.

```
Clients ──gRPC──▶ Ingestion ──Redis Streams──▶ Workers
                      │                           │
                      ◀────── Redis Pub/Sub ◀─────┘
                      │          (results)
Frontend ──HTTP──▶ Gateway ──gRPC──┘
```

The ingestion service subscribes to a result channel *before* publishing the task, so the response is never lost — even under load or with multiple ingestor replicas.

## Services

| Service | What it does | Port |
|---------|-------------|------|
| Ingestion | gRPC server — receives heartbeats, text, file streams | 50051 |
| Worker | Consumer pool — processes text and file chunks | — |
| API | FastAPI REST API, translates HTTP to gRPC | 8080 |
| Redis | Broker (Streams for tasks, Pub/Sub for results) | 6379 |

## Running it

```bash
make up          # builds and starts everything
make logs        # tail all services
make down        # tear down + remove volumes
```

Frontend (separate):

```bash
cd frontend
cp .env.local.example .env.local
npm install && npm run dev
```

Tests (services must be running):

```bash
make test
```

## Project layout

```
common/broker.py             Shared Redis broker (Streams + Pub/Sub)
services/ingestion/          gRPC server, receives and enqueues work
services/worker/             Async worker pool (text + file processors)
services/gateway/            HTTP API gateway (FastAPI)
frontend/                    Next.js dashboard
proto/edgescale.proto        Protobuf definitions
tests/                       Concurrent and resilience tests
```

## Scaling

Workers scale horizontally via Redis consumer groups — each task is delivered to exactly one consumer. Add replicas and Redis distributes automatically.

```bash
docker compose up --scale worker=5 -d
```

Ingestors also scale. Each request subscribes to a unique Pub/Sub channel (`result:{uuid}`), so results route back to the correct instance regardless of how many are running.

## Config

All env vars, all optional with sane defaults:

| Variable | Default | What |
|----------|---------|------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `GRPC_PORT` | `50051` | Ingestion listen port |
| `GATEWAY_PORT` | `8080` | Gateway listen port |
| `WORKER_CONCURRENCY` | `4` | Async tasks per worker instance |
| `TEXT_STREAM_KEY` | `text_tasks` | Redis stream for text jobs |
| `FILE_STREAM_KEY` | `file_tasks` | Redis stream for file jobs |
| `MAX_STREAM_LENGTH` | `10000` | Backpressure cap |
| `RESULT_TIMEOUT` | `30.0` | Text result timeout (s) |
| `FILE_RESULT_TIMEOUT` | `60.0` | File result timeout (s) |
| `LOG_LEVEL` | `INFO` | Log verbosity |

## Deployment

Backend is containerized. Push images to your registry, run on whatever — Kubernetes, Serverless Containers, a single VM with Compose. Redis can be managed or self-hosted.

Frontend deploys to Vercel. Set `NEXT_PUBLIC_API_URL` to your gateway's public URL.

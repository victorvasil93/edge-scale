# EdgeScale — Large Scale Event Processor

A high-scale ingestion and processing pipeline for edge device telemetry, built with **gRPC**, **Redis Streams**, and **Python asyncio**.

## Architecture

```
Edge Devices ──gRPC/HTTP2──▶ Ingestion Service ──Redis Streams──▶ Worker Pool
                                    │                                  │
                                    ◀─────── Redis Pub/Sub ◀───────────┘
                                    │              (results)
                                    │
Frontend ──REST/HTTP──▶ Gateway ──gRPC──┘
(Vercel)               (FastAPI)
```

### Request-Response over Async Broker

The core pattern enables synchronous-feeling gRPC responses while using fully async processing:

1. **Ingestion Service** receives a gRPC call (e.g. `AnalyzeText`)
2. Generates a unique `request_id` and **subscribes** to a Redis Pub/Sub channel `result:{request_id}`
3. Publishes the task to a Redis Stream (`text_tasks` / `file_tasks`)
4. **Worker** picks up the task from the stream via consumer groups, processes it, and **publishes** the result to the Pub/Sub channel
5. Ingestion receives the result and returns it to the client

This ensures the gRPC caller gets an immediate response while all heavy processing is decoupled through the broker.

### Services

| Service | Role | Port |
|---------|------|------|
| **Ingestion** | gRPC server — heartbeats, text analysis, file streaming | `50051` |
| **Worker** | Consumer pool — text word count, file chunk processing | — |
| **Gateway** | REST API for the frontend (translates HTTP → gRPC) | `8080` |
| **Redis** | Message broker (Streams + Pub/Sub) | `6379` |

### Key Design Decisions

- **Backpressure**: Stream length is capped (`MAX_STREAM_LENGTH`). When full, the ingestion service returns `RESOURCE_EXHAUSTED` / HTTP 429 so clients can retry with backoff.
- **Concurrency**: Workers use Redis consumer groups for load distribution. Multiple worker replicas with configurable internal concurrency (`WORKER_CONCURRENCY`).
- **Efficiency**: File uploads use gRPC client-to-server streaming. Chunks are forwarded to Redis without buffering the full file. The file worker uses an atomic Lua script for running word count accumulation.
- **Observability**: All services emit structured JSON logs with request tracing fields (`request_id`, `file_id`, `agent_id`).

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for the frontend)
- Python 3.12+ (for running tests locally)

### One-Command Deploy

```bash
make up
```

This builds and starts all backend services (Redis, Ingestion, Workers, Gateway).

### Start the Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Run Tests

```bash
# With services already running:
cd tests
pip install -r requirements.txt
pytest -v .
```

Or all-in-one:

```bash
make test
```

## Project Structure

```
edge-scale/
├── proto/                        Protobuf service definitions
│   └── edgescale.proto
├── common/                       Shared Python library (no config — stateless)
│   ├── broker.py                 Redis Streams + Pub/Sub broker
│   └── observability.py          Structured JSON logging
├── services/
│   ├── ingestion/                Service A — gRPC ingestion server
│   │   ├── main.py
│   │   └── config.py             IngestionConfig (REDIS_URL, GRPC_PORT, timeouts)
│   ├── worker/                   Service B — text & file worker pool
│   │   ├── main.py
│   │   ├── config.py             WorkerConfig (REDIS_URL, concurrency, consumer group)
│   │   └── workers/
│   │       ├── text.py           Text word count worker
│   │       └── file.py           File chunk worker (Lua-based atomic counting)
│   └── gateway/                  REST gateway (FastAPI)
│       ├── main.py
│       └── config.py             GatewayConfig (gRPC host/port, gateway port)
├── frontend/                     Next.js dashboard (Vercel-ready)
├── tests/                        Integration & resilience tests
├── scripts/                      Proto generation helpers
├── docker-compose.yml            Full stack orchestration
├── Makefile                      Development shortcuts
└── README.md
```

Each service owns its own `config.py` with only the environment variables it needs. The `common/` library is stateless — `Broker` accepts connection parameters via constructor, `setup_logging()` accepts the level as an argument.

## Deployment

### Backend (Scaleway)

All backend services are containerized. Deploy to Scaleway using:

- **Scaleway Container Registry**: Push Docker images
- **Scaleway Serverless Containers** or **Kubernetes (Kapsule)**: Run the services
- **Scaleway Managed Redis** (or deploy Redis via container)

```bash
# Build and push images
docker compose build
docker tag edge-scale-ingestion:latest rg.fr-par.scw.cloud/<namespace>/ingestion:latest
docker tag edge-scale-worker:latest rg.fr-par.scw.cloud/<namespace>/worker:latest
docker tag edge-scale-gateway:latest rg.fr-par.scw.cloud/<namespace>/gateway:latest
docker push rg.fr-par.scw.cloud/<namespace>/ingestion:latest
docker push rg.fr-par.scw.cloud/<namespace>/worker:latest
docker push rg.fr-par.scw.cloud/<namespace>/gateway:latest
```

### Frontend (Vercel)

1. Push the `frontend/` directory to a Git repo
2. Import into Vercel
3. Set the environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-gateway.scw.cloud
   ```
4. Deploy

## Configuration

All services are configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `GRPC_PORT` | `50051` | Ingestion gRPC listen port |
| `GATEWAY_PORT` | `8080` | Gateway HTTP listen port |
| `WORKER_CONCURRENCY` | `4` | Async tasks per worker instance |
| `MAX_STREAM_LENGTH` | `10000` | Backpressure threshold |
| `RESULT_TIMEOUT` | `30.0` | Text analysis timeout (seconds) |
| `FILE_RESULT_TIMEOUT` | `60.0` | File analysis timeout (seconds) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Test Script Details

The test suite simulates concurrent edge agents:

- **`test_concurrent.py`**: 100 concurrent heartbeats, 50 concurrent text analyses (with correctness validation), 10 concurrent file uploads (100KB-1MB)
- **`test_resilience.py`**: 200-request sustained burst (validates graceful backpressure), 500 rapid-fire heartbeats, large payload handling (100K words), edge cases

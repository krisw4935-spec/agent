# Docker

## Services

```mermaid
graph TB
    subgraph stack["Full stack (make stack-up)"]
        app["app\n(FastAPI, port 8000)"]
        db["db\n(PostgreSQL + pgvector, port 5432)"]
        valkey["valkey\n(Valkey/Redis, port 6379)"]
        prometheus["prometheus\n(port 9090)"]
        grafana["grafana\n(port 3000)"]
        cadvisor["cadvisor\n(container metrics, port 8080)"]
        
        subgraph langfuse["Langfuse Cluster"]
            lf_web["langfuse-web\n(port 3001)"]
            lf_worker["langfuse-worker\n(async processing)"]
            clickhouse["clickhouse\n(OLAP, port 8123/9000)"]
            minio["minio\n(S3 storage, port 9001/9002)"]
        end
    end

    app --> db
    app -.->|"optional cache\n(set VALKEY_HOST=valkey)"| valkey
    app -->|"traces\n(set LANGFUSE_HOST)"| lf_web
    lf_web --> db
    lf_web --> clickhouse
    lf_web --> minio
    lf_web --> valkey
    lf_worker --> db
    lf_worker --> clickhouse
    lf_worker --> minio
    lf_worker --> valkey
    prometheus -->|"scrapes /metrics"| app
    prometheus -->|"scrapes container stats"| cadvisor
    grafana --> prometheus
```

Valkey is always started but only used by the app when `VALKEY_HOST=valkey` is set in your `.env` file. Without it the app falls back to an in-memory cache.

## Commands

### API + database only (most common for development)

```bash
make docker-up ENV=development     # start
make docker-down ENV=development   # stop
make docker-logs ENV=development   # tail logs
```

### Langfuse cluster only

```bash
make langfuse-up ENV=development   # start Langfuse + ClickHouse + MinIO + DB + Valkey
make langfuse-down ENV=development # stop Langfuse cluster
make langfuse-logs ENV=development # tail Langfuse cluster logs
```

### Full stack (includes Prometheus + Grafana + Langfuse)

```bash
make stack-up ENV=development      # start everything
make stack-down ENV=development    # stop everything
make stack-logs ENV=development    # tail all service logs
```

### Build a custom image

```bash
make docker-build ENV=production
```

This runs `scripts/build-docker.sh` which builds and tags the image for the specified environment.

## Running migrations inside Docker

After `make docker-up`, run migrations against the containerised database:

```bash
make migrate ENV=development
```

This sources the correct `.env` file and runs `alembic upgrade head` from your local machine, connecting to the containerised PostgreSQL.

## Environment files

Each environment needs a `.env.<env>` file:

```bash
cp .env.example .env.development
cp .env.example .env.staging
cp .env.example .env.production
```

The `docker-up` and `stack-up` commands pass the env file to Docker Compose via `--env-file`. Make sure `POSTGRES_HOST=db` in your Docker env files (not `localhost`) — the service name within the Compose network is `db`.

## Langfuse Self-Hosted

After `make langfuse-up` (or `make stack-up`), Langfuse Web UI is available at [http://localhost:3001](http://localhost:3001).

1. Open [http://localhost:3001](http://localhost:3001) in your browser.
2. Sign up your first admin account.
3. Create an organization and project.
4. Go to **Settings -> API Keys** and generate a new key pair (`pk-lf-...` and `sk-lf-...`).
5. Copy keys to your `.env.<env>`:
   ```env
   LANGFUSE_TRACING_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=http://localhost:3001   # or http://langfuse-web:3000 inside Docker
   ```

## Grafana

After `make stack-up`, Grafana is available at [http://localhost:3000](http://localhost:3000).

Default credentials: `admin` / `admin`

Pre-configured dashboards (in `grafana/`):

- API performance (request rate, latency, error rate)
- Rate limiting statistics
- Database connection pool health
- System resource usage

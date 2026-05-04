# PostgreSQL Relational Database Setup

## Overview

PostgreSQL stores structured data: user accounts, session history, document metadata, and audit logs.

## Prerequisites

Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop).

## Start PostgreSQL

```bash
docker compose up -d
docker compose ps          # Verify it's running
```

## Environment Variables (.env)

Add these to your `.env` file:

```env
POSTGRES_HOST=postgres         # Docker service name
POSTGRES_PORT=5432
POSTGRES_DB=coach_db
POSTGRES_USER=coach_user
POSTGRES_PASSWORD=your_password
```

## Python Integration

The `postgres_client.py` module provides async database access. Here's a simple example:

```python
import asyncio
from app.data_access.clients.postgres_client import PostgresClient

async def test():
    client = PostgresClient(
        host="localhost",
        port=5432,
        database="coach_db",
        user="coach_user",
        password="your_password"
    )
    
    await client.connect()
    
    try:
        # Run a query
        result = await client.fetch("SELECT version();")
        print(result)
    finally:
        await client.disconnect()

asyncio.run(test())
```

In your FastAPI routes, the PostgreSQL client is injected via `dependencies.py`.

## Connect to Database

Using `psql`:

```bash
docker compose exec postgres psql -U coach_user -d coach_db
```

Common commands:
```sql
\dt      -- List tables
\d table -- Describe table
\q      -- Exit
```

## Troubleshooting

**Container won't start**
- Check Docker is running: `docker compose logs postgres`

**Connection refused**
- Verify container is running: `docker compose ps`
- Check credentials in `.env` match `docker-compose.yml`

**Port 5432 already in use**
- Change `POSTGRES_PORT` to another port in `.env` (e.g., `5433`)

**Lost data**
- Don't delete `postgres_data/` folder. Use: `docker compose down -v`

## How It Fits Together

- **Ollama**: Generates vector embeddings
- **Qdrant**: Stores embeddings for semantic search
- **PostgreSQL**: Stores user data, sessions, and document metadata

That's all you need to get started!

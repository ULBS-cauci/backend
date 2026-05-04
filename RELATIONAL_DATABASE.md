# PostgreSQL Local Setup Guide

This guide shows you how to securely run a local PostgreSQL database using Docker Compose and connect it to our Python backend.

## What You Are Setting Up

PostgreSQL is our primary relational database for application state, user data, and metadata. In this project, it runs as a Docker container and listens for TCP connections on port `5432`.

The Compose file used is:

- `docker-compose.yml`

## Prerequisites

You need all of the following:

1. Docker Desktop installed and running.
2. Docker Compose available (`docker compose` command).
3. Port `5432` free on your machine.
4. Python virtual environment created and activated.

## 1) Open Terminal in This Folder

From your project root folder:

```bash
cd backend
```

## 2) Configure Environment Variables (.env)

Your Docker container and Python app both read database credentials from your `.env` file. 

The template `.env.example` looks like this:

```env
# Relational Database (PostgreSQL)
POSTGRES_USER=admin
POSTGRES_PASSWORD=change_me
POSTGRES_DB=postgres_db
```

Create or open your local `.env` file (do not commit this file) and set your real local password:

```env
# Relational Database (PostgreSQL)
POSTGRES_USER=admin
POSTGRES_PASSWORD=1234
POSTGRES_DB=postgres_db
```

**Important:**
- `POSTGRES_PASSWORD` must not be empty.
- Keep production secrets outside git.

## 3) Verify Docker Compose Configuration

Ensure your `docker-compose.yml` uses the variables from your `.env` file. The PostgreSQL service should look like this:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: postgres_db
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
```

## 4) Start PostgreSQL

Run this command in the same folder as `docker-compose.yml`:

```bash
docker compose up -d
```

What this does:
- Downloads `postgres:15-alpine` (first run only).
- Starts container `postgres_db`.
- Maps local port `5432` to container port `5432`.
- Creates a local folder `postgres_data` so your tables and rows survive container restarts.

## 5) Check Container Status

```bash
docker compose ps
```

You should see service `postgres_db` as `Up`.

## 6) Verify Database Is Reachable

PostgreSQL does not speak HTTP, so **you cannot check it in a web browser**. Verify it using one of these methods:

### Method A: Database Client (Recommended)
Open DBeaver, pgAdmin, or the VS Code Database Client extension and connect using:
- **Host:** `localhost`
- **Port:** `5432`
- **User:** `admin`
- **Password:** `1234` (or whatever you set in `.env`)
- **Database:** `postgres_db`

### Method B: Backend Availability Check
If you want to confirm the FastAPI app itself is running, start your backend server using the project's documented backend setup/start instructions, then open `http://localhost:8000/`.

This only verifies that the backend process is up. It does **not** verify PostgreSQL connectivity, because the current app does not yet expose a database-backed endpoint in Swagger or elsewhere.

Use **Method A** to verify that the database is reachable until a dedicated database health-check route is added.

## 7) Stop / Restart

Stop container safely:

```bash
docker compose down
```

Start again:

```bash
docker compose up -d
```

Data remains intact because of volume mapping: `./postgres_data:/var/lib/postgresql/data`

## 8) Reset Local Data (Danger)

If you want a completely clean relational database, stop the container and remove the local data folder:

```bash
docker compose down
rm -rf postgres_data
docker compose up -d
```

*Note: This permanently deletes all local tables and rows.*

## Common Problems and Fixes

### Port 5432 already in use
**Symptom:** Container fails to start.
**Fix:** 1. Stop the local Postgres installation using `5432` on your machine.
2. Or change `POSTGRES_PORT` in your `.env` file (for example, to `5433`) and restart with `docker compose down` then `docker compose up -d`.

### Variable is not set (Defaulting to a blank string)
**Symptom:** Yellow warning messages in the terminal when running `docker compose up -d`.
**Fix:** - Docker cannot find your `.env` file. 
- Ensure you copied `.env.example` to exactly `.env` (no `.txt` extension).
- Ensure `.env` is in the exact same folder as `docker-compose.yml`.
- Run `docker compose down` then `docker compose up -d` to reload the file.

### Browser shows ERR_EMPTY_RESPONSE
**Symptom:** Navigating to `http://localhost:5432` in Chrome/Edge fails.
**Fix:** This is normal! Postgres uses a TCP binary protocol, not HTTP. Use a database client to view tables instead.

## Useful Day-to-Day Commands

Start in background:
```bash
docker compose up -d
```

See running services:
```bash
docker compose ps
```

Follow logs:
```bash
docker compose logs -f postgres
```

Stop and remove container:
```bash
docker compose down
```

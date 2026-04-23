# Backend Setup Guide

This folder contains the Python backend setup and dependency workflow.

## Project Structure

- `requirements.txt` -> Python dependencies
- `.env.example` -> Environment variable template
- `.env` -> Ask team for the production .env
- `qdrant/README.md` -> Qdrant-specific setup and usage guide

## Prerequisites

- Git
- Python 3.10+ (recommended)
- pip (comes with Python)

## 1) Clone the Project

git clone <YOUR_REPOSITORY_URL>
cd ULBS-coach/backend

Replace `<YOUR_REPOSITORY_URL>` with your actual repository URL.

## 2) Create and Activate a Virtual Environment

Run these commands inside the `backend` folder.

### Linux

- python3 -m venv .venv
- source .venv/bin/activate
- python -m pip install --upgrade pip
- pip install -r requirements.txt

### macOS

- python3 -m venv .venv
- source .venv/bin/activate
- python -m pip install --upgrade pip
- pip install -r requirements.txt

### Windows (PowerShell)

- py -m venv .venv
- .\.venv\Scripts\Activate.ps1
- python -m pip install --upgrade pip
- pip install -r requirements.txt

If PowerShell blocks activation, run this once in PowerShell as Administrator:

Set-ExecutionPolicy RemoteSigned

### Windows (Command Prompt)

- py -m venv .venv
- .venv\Scripts\activate.bat
- python -m pip install --upgrade pip
- pip install -r requirements.txt

## 3) Environment Variables (.env)

Create your local `.env` from `.env.example`.

### Linux/macOS

cp .env.example .env

### Windows (PowerShell)

Copy-Item .env.example .env

Then edit (ask teammates for production .env) `.env` and set real values (remove `#` and spaces around `=`).

For Qdrant-related environment variables and examples, see `qdrant/README.md`.

## When adding a new dependency

1. Activate your virtual environment.
2. Install the package:

- pip install package-name

3. Regenerate locked dependencies:

- pip freeze > requirements.txt

4. Commit both your code changes and `requirements.txt`.

## Keep .env.example Updated (Important)

Whenever you add a new environment variable in code:

1. Add it to `.env.example`.
2. Keep values empty or placeholder-only (never commit secrets).
3. Add a short inline comment explaining the variable.
4. Mention whether it is required or optional.
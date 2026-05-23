# Seed Materials Folder

Place PDF files here to use with `python -m scripts.seed --embed`.

## How it works

When you run the seeder with `--embed`, it:

1. Reads every `*.pdf` from this folder (sorted alphabetically).
2. Randomly picks **2 professor-held courses** from the seeded courses.
3. Distributes the PDFs across those 2 courses (alternating: even-indexed → course A, odd-indexed → course B).
4. Runs each PDF through the full ingestion pipeline:
   - Text extraction (pypdf)
   - Text splitting (LangChain splitter)
   - Dense embedding (Ollama)
   - Sparse encoding (BGE-M3)
   - Qdrant upsert (dense + sparse vectors)
   - MinIO upload
   - `Material` DB record

## Requirements before running

```bash
docker-compose up -d   # Qdrant, MinIO, and Postgres must be running
# Ollama must be running with the embedding model loaded:
ollama run my-project-embed
```

## Example commands

```bash
cd backend
.venv\Scripts\activate

# Use this folder (default):
python -m scripts.seed --embed

# Use a custom folder:
python -m scripts.seed --embed path/to/your/pdfs

# Wipe everything and re-embed:
python -m scripts.seed --reset --embed

# Preview what would happen without touching anything:
python -m scripts.seed --embed --dry-run
```

## Notes

- **Not idempotent**: unlike mock mode, each `--embed` run creates new Material records
  with fresh UUIDs (assigned by FileService). Use `--reset --embed` to cleanly re-embed.
- **Only 2 courses receive materials**, regardless of how many PDFs are in this folder.
- This folder is `.gitignore`d (PDFs can be large). Add your own `.gitignore` entry if needed.
- The BGE-M3 sparse encoder model (~570 MB) is downloaded on first use and cached by HuggingFace.

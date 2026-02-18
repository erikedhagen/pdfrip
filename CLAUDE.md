# PDF Image Extractor

PDF extraction tool that pulls embedded raster images, vector graphics, and separated vector/text layers from PDF files. Available as a web app and CLI.

## Tech Stack

- Python 3.12, managed with `uv`
- FastAPI + Uvicorn (web server)
- PyMuPDF (`fitz`) for PDF parsing and rendering

## Setup & Run

```bash
uv sync                              # Install dependencies
uvicorn main:app --reload             # Dev server on :8000
uv run extract_images.py input.pdf    # CLI extraction
uv run extract_images.py --layers input.pdf  # CLI with layer separation
```

Production: `uvicorn main:app --host 0.0.0.0 --port 8000` (see Procfile)

## Project Structure

- `pdf_extract.py` — Core extraction engine (shared by web and CLI). Handles content stream tokenization, spatial clustering of vector regions, and vector/text layer separation.
- `main.py` — FastAPI web server. Serves upload form at `/`, processes PDFs at `POST /extract`, returns ZIP.
- `extract_images.py` — CLI wrapper for batch processing.

## Architecture Notes

- **Layer separation** works by manipulating PDF content streams: removing BT/ET blocks for vector-only output, neutralizing paint operators (S, s, f, F, etc.) for text-only output.
- **Spatial clustering** (`_cluster_rects()`) merges nearby vector regions to avoid fragmentation.
- Renders at 200 DPI by default. Skips regions < 5x5px and full-page backgrounds.
- Unicode filenames use RFC 5987 encoding with ASCII fallback.

## Conventions

- Use `uv` for all dependency management (not pip)
- Core logic stays in `pdf_extract.py`; delivery layers (web/CLI) stay thin
- No database or persistence — purely functional processing

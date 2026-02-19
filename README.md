# PDFPeel

Extract embedded raster images, vector graphics, and separated vector/text layers from PDF files.

## Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd pdfpeel
uv sync
```

## Web App

```bash
uv run uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000), upload a PDF, and download the extracted images as a ZIP.

For production:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## CLI

```bash
uv run extract_images.py input.pdf [output_dir]
```

With vector/text layer separation:

```bash
uv run extract_images.py --layers input.pdf [output_dir]
```

## Export Modes

- **Combined** — Vectors and text merged into one image per region
- **Separate layers** — Matched-dimension vector-only and text-only PNGs for each region

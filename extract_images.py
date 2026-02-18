#!/usr/bin/env python3
"""Extract all images and vector graphics from a PDF file.

Usage:
    uv run extract_images.py input.pdf [output_dir]
    uv run extract_images.py --layers input.pdf [output_dir]
"""
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///

import sys
from pathlib import Path

import fitz  # pymupdf

from pdf_extract import extract_all


def main(pdf_path: str, output_dir: str | None = None, *, layers: bool = False) -> None:
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    out = Path(output_dir) if output_dir else pdf.parent / f"{pdf.stem}_images"
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    images = extract_all(doc, layers=layers)
    doc.close()

    for filename, data in images:
        (out / filename).write_bytes(data)
        print(f"  Saved {filename} ({len(data)} bytes)")

    print(f"\nExtracted {len(images)} item(s) to {out}/")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_layers = "--layers" in args
    if use_layers:
        args.remove("--layers")

    if not args:
        print("Usage: uv run extract_images.py [--layers] <input.pdf> [output_dir]")
        sys.exit(1)

    main(args[0], args[1] if len(args) > 1 else None, layers=use_layers)

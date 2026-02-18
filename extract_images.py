#!/usr/bin/env python3
"""Extract all images from a PDF file.

Usage:
    uv run extract_images.py input.pdf [output_dir]
"""
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///

import sys
from pathlib import Path

import fitz  # pymupdf


def extract_images(pdf_path: str, output_dir: str | None = None) -> None:
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    out = Path(output_dir) if output_dir else pdf.parent / f"{pdf.stem}_images"
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    count = 0

    for page_num in range(len(doc)):
        for img_index, img in enumerate(doc.get_page_images(page_num, full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            if not base_image:
                continue

            ext = base_image["ext"]
            image_bytes = base_image["image"]

            filename = f"page{page_num + 1}_img{img_index + 1}.{ext}"
            (out / filename).write_bytes(image_bytes)
            count += 1
            print(f"  Saved {filename} ({len(image_bytes)} bytes)")

    doc.close()
    print(f"\nExtracted {count} image(s) to {out}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run extract_images.py <input.pdf> [output_dir]")
        sys.exit(1)

    extract_images(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

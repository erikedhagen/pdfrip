"""Shared PDF extraction logic for both CLI and web.

Supports extracting:
- Embedded raster images
- Vector graphics (rendered as PNG)
- Separate vector/text layers for overlapping regions
"""

from __future__ import annotations

import fitz


# ---------------------------------------------------------------------------
# PDF content-stream tokenizer & layer filters
# ---------------------------------------------------------------------------

def _tokenize(stream: bytes):
    """Yield (raw_bytes, token_type) from a PDF content stream.

    token_type is one of: "ws", "string", "hexstring", "token".
    Every byte of the input is accounted for in the output so that
    b"".join(raw for raw, _ in _tokenize(stream)) == stream.
    """
    i = 0
    n = len(stream)
    WS = b" \n\r\t\x00\x0c"
    DELIMS = b"()<>[]{}/%"

    while i < n:
        c = stream[i : i + 1]

        # --- whitespace run ---
        if c[0] in WS:
            start = i
            while i < n and stream[i : i + 1][0] in WS:
                i += 1
            yield stream[start:i], "ws"
            continue

        # --- string literal (...) ---
        if c == b"(":
            start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                ch = stream[i : i + 1]
                if ch == b"\\":
                    i += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                i += 1
            yield stream[start:i], "string"
            continue

        # --- hex string <...> (not dict <<) ---
        if c == b"<" and stream[i + 1 : i + 2] != b"<":
            start = i
            i = stream.index(b">", i) + 1
            yield stream[start:i], "hexstring"
            continue

        # --- comment %... ---
        if c == b"%":
            start = i
            while i < n and stream[i : i + 1] not in (b"\n", b"\r"):
                i += 1
            yield stream[start:i], "ws"  # treat comments as whitespace
            continue

        # --- everything else: operator / operand token ---
        # includes numbers, names (/Foo), booleans, dict delims, arrays, operators
        start = i
        if c == b"/" or c == b"[" or c == b"]":
            # name or array delimiters — scan until next delimiter/ws
            i += 1
            if c == b"/":
                while i < n and stream[i : i + 1][0] not in WS and stream[i : i + 1][0] not in DELIMS:
                    i += 1
        elif stream[i : i + 2] in (b"<<", b">>"):
            i += 2
        else:
            i += 1
            while i < n and stream[i : i + 1][0] not in WS and stream[i : i + 1][0] not in DELIMS:
                i += 1

        yield stream[start:i], "token"


_PAINT_OPS = frozenset({b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"})


def _strip_text(stream: bytes) -> bytes:
    """Remove BT … ET text blocks from a content stream."""
    result = bytearray()
    in_text = False
    for raw, ttype in _tokenize(stream):
        if ttype == "token":
            if raw == b"BT":
                in_text = True
                continue
            if raw == b"ET":
                in_text = False
                continue
        if not in_text:
            result.extend(raw)
    return bytes(result)


def _strip_vectors(stream: bytes) -> bytes:
    """Neutralise path-painting operators (replace with ``n``) so vectors vanish."""
    result = bytearray()
    for raw, ttype in _tokenize(stream):
        if ttype == "token" and raw in _PAINT_OPS:
            result.extend(b"n")
        else:
            result.extend(raw)
    return bytes(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cluster_rects(rects: list[fitz.Rect], gap: float = 20.0) -> list[fitz.Rect]:
    """Merge overlapping / nearby rectangles into clusters."""
    if not rects:
        return []
    clusters = [fitz.Rect(r) for r in rects]
    merged = True
    while merged:
        merged = False
        new_clusters: list[fitz.Rect] = []
        used: set[int] = set()
        for i, a in enumerate(clusters):
            if i in used:
                continue
            expanded = fitz.Rect(a.x0 - gap, a.y0 - gap, a.x1 + gap, a.y1 + gap)
            for j in range(i + 1, len(clusters)):
                if j in used:
                    continue
                if expanded.intersects(clusters[j]):
                    a |= clusters[j]
                    expanded = fitz.Rect(a.x0 - gap, a.y0 - gap, a.x1 + gap, a.y1 + gap)
                    used.add(j)
                    merged = True
            new_clusters.append(a)
            used.add(i)
        clusters = new_clusters
    return clusters


def _page_drawing_clusters(page: fitz.Page) -> list[fitz.Rect]:
    """Return clustered bounding boxes of vector drawings on *page*."""
    drawings = page.get_drawings()
    if not drawings:
        return []
    rects: list[fitz.Rect] = []
    for d in drawings:
        r = fitz.Rect(d["rect"])
        if r.width < 5 or r.height < 5:
            continue
        if r.width >= page.rect.width * 0.98 and r.height >= page.rect.height * 0.98:
            continue
        rects.append(r)
    return _cluster_rects(rects)


def _render_clip(page: fitz.Page, clip: fitz.Rect, dpi: int) -> bytes:
    """Render a clipped region of *page* as PNG bytes."""
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    return pix.tobytes("png")


def _padded_clip(clip: fitz.Rect, page_rect: fitz.Rect, pad: float = 5.0) -> fitz.Rect:
    clip = clip + fitz.Rect(-pad, -pad, pad, pad)
    clip &= page_rect
    return clip


def _make_temp_page(doc: fitz.Document, page_num: int) -> tuple[fitz.Document, fitz.Page]:
    """Create a temporary single-page document from *page_num*."""
    tmp = fitz.open()
    tmp.insert_pdf(doc, from_page=page_num, to_page=page_num)
    page = tmp[0]
    page.clean_contents()
    return tmp, page


def _modify_stream(doc: fitz.Document, page: fitz.Page, fn) -> None:
    """Apply *fn* to every content stream of *page* in *doc*."""
    for xref in page.get_contents():
        stream = doc.xref_stream(xref)
        doc.update_stream(xref, fn(stream))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_all(
    doc: fitz.Document,
    *,
    dpi: int = 200,
    layers: bool = False,
) -> list[tuple[str, bytes]]:
    """Extract graphics from a PDF document.

    If *layers* is False (default), embedded raster images and rasterised
    vector clusters are returned.

    If *layers* is True, each vector cluster that overlaps with text produces
    two PNGs at **identical dimensions** — one with vectors only and one with
    text only — so they can be reassembled later.
    """
    results: list[tuple[str, bytes]] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        prefix = f"page{page_num + 1}"

        # ---- embedded raster images ----
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base = doc.extract_image(xref)
            if not base:
                continue
            results.append((f"{prefix}_img{img_idx + 1}.{base['ext']}", base["image"]))

        # ---- vector graphic clusters ----
        clusters = _page_drawing_clusters(page)
        if not clusters:
            continue

        for cl_idx, raw_clip in enumerate(clusters):
            clip = _padded_clip(raw_clip, page.rect)
            if clip.width < 15 or clip.height < 15:
                continue

            tag = f"{prefix}_vec{cl_idx + 1}"

            if not layers:
                # Single combined render (original behaviour)
                results.append((f"{tag}.png", _render_clip(page, clip, dpi)))
                continue

            # --- layer mode: separate vector & text renders ---

            # Vector-only: remove text
            vec_doc, vec_page = _make_temp_page(doc, page_num)
            _modify_stream(vec_doc, vec_page, _strip_text)
            results.append((f"{tag}_vector.png", _render_clip(vec_page, clip, dpi)))
            vec_doc.close()

            # Text-only: remove vectors
            txt_doc, txt_page = _make_temp_page(doc, page_num)
            _modify_stream(txt_doc, txt_page, _strip_vectors)
            results.append((f"{tag}_text.png", _render_clip(txt_page, clip, dpi)))
            txt_doc.close()

    return results

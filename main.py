import io
import zipfile
from pathlib import Path
from urllib.parse import quote

import fitz  # pymupdf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from pdf_extract import extract_all

app = FastAPI()

HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDF Image Extractor</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f5f5f5; display: flex;
           justify-content: center; align-items: center; min-height: 100vh; }
    .card { background: #fff; border-radius: 12px; padding: 2.5rem; max-width: 420px;
            width: 100%; box-shadow: 0 2px 12px rgba(0,0,0,0.08); text-align: center; }
    h1 { font-size: 1.4rem; margin-bottom: 0.5rem; }
    p { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .upload-label { display: block; border: 2px dashed #ccc; border-radius: 8px; padding: 2rem;
            cursor: pointer; transition: border-color 0.2s; margin-bottom: 1rem; }
    .upload-label:hover { border-color: #888; }
    input[type="file"] { display: none; }
    .filename { font-size: 0.85rem; color: #333; margin-bottom: 1rem; min-height: 1.2em; }
    .mode-group { text-align: left; margin-bottom: 1.5rem; }
    .mode-group span { display: block; font-size: 0.8rem; color: #999; margin-bottom: 0.5rem;
                       text-transform: uppercase; letter-spacing: 0.05em; }
    .mode-group label { display: flex; align-items: center; gap: 0.5rem;
                        font-size: 0.9rem; color: #333; padding: 0.4rem 0; cursor: pointer; }
    .mode-group input[type="radio"] { display: inline; accent-color: #111; }
    .hint { font-size: 0.75rem; color: #999; margin-left: 1.5rem; }
    button { background: #111; color: #fff; border: none; border-radius: 8px;
             padding: 0.75rem 2rem; font-size: 1rem; cursor: pointer; width: 100%; }
    button:hover { background: #333; }
  </style>
</head>
<body>
  <div class="card">
    <div style="margin-bottom: 1rem;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="72" height="72">
        <rect x="12" y="18" width="44" height="58" rx="2" fill="#d8d8d8" stroke="#222" stroke-width="2"/>
        <rect x="18" y="12" width="44" height="58" rx="2" fill="#ededed" stroke="#222" stroke-width="2"/>
        <g transform="rotate(-4,66,56)">
          <rect x="42" y="30" width="44" height="58" rx="2" fill="#fff" stroke="#222" stroke-width="2.5"/>
          <polyline points="50,64 56,54 60,60 66,50 72,64" fill="none" stroke="#222" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="54" cy="46" r="3.5" fill="none" stroke="#222" stroke-width="1.5"/>
        </g>
      </svg>
    </div>
    <h1>PDF Image Extractor</h1>
    <p>Upload a PDF to extract embedded images and vector graphics.</p>
    <form action="/extract" method="post" enctype="multipart/form-data">
      <label class="upload-label">
        <span id="label-text">Click to select a PDF</span>
        <input type="file" name="file" accept=".pdf" required
               onchange="document.getElementById('fname').textContent = this.files[0]?.name || '';
                         document.getElementById('label-text').textContent = this.files[0] ? 'File selected' : 'Click to select a PDF';">
      </label>
      <div class="filename" id="fname"></div>
      <div class="mode-group">
        <span>Export mode</span>
        <label><input type="radio" name="mode" value="combined" checked> Combined</label>
        <div class="hint">Vectors and text merged into one image per region</div>
        <label><input type="radio" name="mode" value="layers"> Separate layers</label>
        <div class="hint">Vector-only and text-only PNGs at matching dimensions</div>
      </div>
      <button type="submit">Extract</button>
    </form>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FORM


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    mode: str = Form("combined"),
):
    pdf_bytes = await file.read()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = extract_all(doc, layers=(mode == "layers"))
    doc.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in images:
            zf.writestr(name, data)
    buf.seek(0)

    stem = Path(file.filename).stem if file.filename else "images"
    zipname = f"{stem}_images.zip"
    ascii_name = zipname.encode("ascii", errors="replace").decode("ascii")
    utf8_name = quote(zipname)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
        },
    )

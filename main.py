import io
import tempfile
import zipfile
from pathlib import Path

import fitz  # pymupdf
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

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
    label { display: block; border: 2px dashed #ccc; border-radius: 8px; padding: 2rem;
            cursor: pointer; transition: border-color 0.2s; margin-bottom: 1rem; }
    label:hover { border-color: #888; }
    input[type="file"] { display: none; }
    .filename { font-size: 0.85rem; color: #333; margin-bottom: 1rem; min-height: 1.2em; }
    button { background: #111; color: #fff; border: none; border-radius: 8px;
             padding: 0.75rem 2rem; font-size: 1rem; cursor: pointer; width: 100%; }
    button:hover { background: #333; }
    button:disabled { background: #999; cursor: not-allowed; }
  </style>
</head>
<body>
  <div class="card">
    <h1>PDF Image Extractor</h1>
    <p>Upload a PDF to extract all embedded images as a zip file.</p>
    <form action="/extract" method="post" enctype="multipart/form-data">
      <label id="drop">
        <span id="label-text">Click to select a PDF</span>
        <input type="file" name="file" accept=".pdf" required
               onchange="document.getElementById('fname').textContent = this.files[0]?.name || '';
                         document.getElementById('label-text').textContent = this.files[0] ? 'File selected' : 'Click to select a PDF';">
      </label>
      <div class="filename" id="fname"></div>
      <button type="submit">Extract Images</button>
    </form>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FORM


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    with tempfile.TemporaryDirectory() as tmp:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images: list[tuple[str, bytes]] = []

        for page_num in range(len(doc)):
            for img_index, img in enumerate(doc.get_page_images(page_num, full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue
                ext = base_image["ext"]
                data = base_image["image"]
                filename = f"page{page_num + 1}_img{img_index + 1}.{ext}"
                images.append((filename, data))

        doc.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in images:
            zf.writestr(name, data)
    buf.seek(0)

    stem = Path(file.filename).stem if file.filename else "images"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{stem}_images.zip"'},
    )

import io
import zipfile
from pathlib import Path
from urllib.parse import quote

import fitz  # pymupdf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pdf_extract import extract_all

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDFPeel — Extract Images & Vectors from PDF</title>
  <meta name="description" content="Extract embedded images and vector graphics from any PDF. Free, instant, and private — your files never touch our disk.">
  <link rel="canonical" href="https://pdfpeel.com/">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://pdfpeel.com/">
  <meta property="og:title" content="PDFPeel — Extract Images & Vectors from PDF">
  <meta property="og:description" content="Extract embedded images and vector graphics from any PDF. Free, instant, and private.">
  <meta property="og:image" content="https://pdfpeel.com/static/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="PDFPeel — Extract Images & Vectors from PDF">
  <meta name="twitter:description" content="Extract embedded images and vector graphics from any PDF. Free, instant, and private.">
  <meta name="twitter:image" content="https://pdfpeel.com/static/og-image.png">
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
    .hint { font-size: 0.75rem; color: #999; margin-left: 1.375rem; }
    button { background: #111; color: #fff; border: none; border-radius: 8px;
             padding: 0.75rem 2rem; font-size: 1rem; cursor: pointer; width: 100%; }
    button:hover { background: #333; }
  </style>
</head>
<body>
  <div class="card">
    <div style="margin-bottom: 0.25rem;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="8 8 82 82" width="72" height="72">
        <rect x="12" y="18" width="44" height="58" rx="2" fill="#d8d8d8" stroke="#222" stroke-width="2"/>
        <rect x="18" y="12" width="44" height="58" rx="2" fill="#ededed" stroke="#222" stroke-width="2"/>
        <g transform="rotate(-4,66,56)">
          <rect x="42" y="30" width="44" height="58" rx="2" fill="#fff" stroke="#222" stroke-width="2.5"/>
          <polyline points="50,64 56,54 60,60 66,50 72,64" fill="none" stroke="#222" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="54" cy="46" r="3.5" fill="none" stroke="#222" stroke-width="1.5"/>
        </g>
      </svg>
    </div>
    <h1 style="font-size: 1.4rem; margin-bottom: 1.25rem; letter-spacing: 0.01em;"><span style="font-weight: 700;">PDF</span><span style="font-weight: 400; color: #444;">Peel</span></h1>
    <p>Extract embedded images and vector graphics from any PDF.</p>
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
    <p style="margin-top: 1rem; font-size: 0.78rem; color: #333; display: inline-flex; align-items: center; gap: 4px;">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4a9" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
      Your files stay private. <a href="#" id="privacy-link" style="color: #333; text-decoration: underline;">Learn more</a>
    </p>
  </div>
  <a href="https://digiswede.com" target="_blank" rel="noopener" style="position: fixed; bottom: 1rem; right: 1rem; font-family: system-ui, sans-serif; font-size: 0.72rem; color: #999; text-decoration: none;">Built by Digiswede</a>

  <div id="privacy-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.4);
       z-index:10; justify-content:center; align-items:center;">
    <div style="background:#fff; border-radius:12px; padding:2rem; max-width:420px; width:90%;
         box-shadow:0 4px 24px rgba(0,0,0,0.15); position:relative;">
      <button id="privacy-close" style="position:absolute; top:0.75rem; right:0.75rem; background:none;
              border:none; font-size:1.2rem; cursor:pointer; color:#999; width:auto; padding:0.25rem;">&#x2715;</button>
      <h2 style="font-size:1.1rem; margin-bottom:1rem;">How your data is handled</h2>
      <ul style="text-align:left; font-size:0.85rem; color:#444; line-height:1.6; padding-left:1.2rem;">
        <li>Your PDF is processed <strong>in server memory only</strong> and never written to disk.</li>
        <li>No files or data are retained after processing completes.</li>
        <li>The server runs within the <strong>European Union</strong>.</li>
      </ul>
    </div>
  </div>

  <script>
    const modal = document.getElementById('privacy-modal');
    document.getElementById('privacy-link').addEventListener('click', function(e) {
      e.preventDefault();
      modal.style.display = 'flex';
    });
    document.getElementById('privacy-close').addEventListener('click', function() {
      modal.style.display = 'none';
    });
    modal.addEventListener('click', function(e) {
      if (e.target === modal) modal.style.display = 'none';
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FORM


@app.get("/sitemap.xml")
async def sitemap():
    return PlainTextResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        "    <loc>https://pdfpeel.com/</loc>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>",
        media_type="application/xml",
    )


@app.get("/robots.txt")
async def robots():
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nSitemap: https://pdfpeel.com/sitemap.xml\n"
    )


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

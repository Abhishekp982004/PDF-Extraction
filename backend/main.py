# backend/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import shutil
import uuid
import io
import logging

# Optional heavy deps used if available
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from pdf2image import convert_from_path
    from PIL import Image
except Exception:
    convert_from_path = None
    Image = None

try:
    import pytesseract
    from pytesseract import Output
except Exception:
    pytesseract = None
    Output = None

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pdf-extract")

app = FastAPI(title="PDF Extraction Playground")

# Allow CORS from frontend (development and Vercel). Replace "*" with Vercel domain in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PREVIEW_DIR = os.path.join(BASE_DIR, "previews")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# default DPI used for png previews & pixel-coordinate conversion
PREVIEW_DPI = 150


@app.get("/")
def root():
    return {"message": "PDF Extraction backend running."}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Save uploaded file
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    target = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(target, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        log.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail="Failed to save file")
    return {"filename": filename, "original_name": file.filename}


class ExtractRequest(BaseModel):
    filename: str
    models: list[str] = ["pdfplumber"]


def _safe_file_path(filename: str) -> str:
    # prevent path traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return os.path.join(UPLOAD_DIR, filename)


def _save_preview_png(file_path: str, page_index: int, dpi: int = PREVIEW_DPI) -> str:
    """
    Render a single page to PNG using pdf2image (poppler required).
    Returns path of PNG.
    """
    if convert_from_path is None or Image is None:
        raise HTTPException(status_code=500, detail="pdf2image or PIL not installed on server")

    preview_name = f"{os.path.splitext(os.path.basename(file_path))[0]}_p{page_index}.png"
    preview_path = os.path.join(PREVIEW_DIR, preview_name)
    if os.path.exists(preview_path):
        return preview_path

    # convert single page (pdf2image page numbers start at 1)
    images = convert_from_path(file_path, dpi=dpi, first_page=page_index + 1, last_page=page_index + 1)
    if len(images) == 0:
        raise HTTPException(status_code=500, detail="Failed to render preview")
    image = images[0]
    image.save(preview_path, format="PNG")
    return preview_path


def extract_with_pdfplumber(file_path: str, dpi: int = PREVIEW_DPI):
    """
    Extract text and word-level bounding boxes using pdfplumber.
    BBoxes are converted to pixel coordinates based on dpi (pts -> px via scale = dpi / 72).
    """
    if pdfplumber is None:
        raise HTTPException(status_code=500, detail="pdfplumber not installed on server")

    result = {"pages": []}
    with pdfplumber.open(file_path) as pdf:
        for pindex, page in enumerate(pdf.pages):
            width_pts = page.width
            height_pts = page.height
            scale = dpi / 72.0
            width_px = int(width_pts * scale)
            height_px = int(height_pts * scale)

            # page text
            text = page.extract_text() or ""

            # words with locations
            words = []
            try:
                raw_words = page.extract_words()
                for w in raw_words:
                    # pdfplumber returns x0, top, x1, bottom (top distance from top)
                    x0 = float(w.get("x0", 0.0))
                    top = float(w.get("top", 0.0))
                    x1 = float(w.get("x1", x0))
                    bottom = float(w.get("bottom", top))
                    bbox_px = [
                        int(x0 * scale),
                        int(top * scale),
                        int(x1 * scale),
                        int(bottom * scale),
                    ]
                    words.append({"text": w.get("text", ""), "bbox": bbox_px})
            except Exception:
                words = []

            # tables (simple extraction)
            tables = []
            try:
                raw_tables = page.extract_tables()
                for t in raw_tables:
                    tables.append({"rows": t})
            except Exception:
                tables = []

            result["pages"].append(
                {
                    "page_number": pindex,
                    "width_pts": width_pts,
                    "height_pts": height_pts,
                    "width_px": width_px,
                    "height_px": height_px,
                    "text": text,
                    "words": words,
                    "tables": tables,
                }
            )
    return result


def extract_with_tesseract(file_path: str, dpi: int = PREVIEW_DPI):
    """
    Rasterize pages and run pytesseract to get OCR words and bounding boxes.
    """
    if convert_from_path is None or pytesseract is None:
        raise HTTPException(status_code=500, detail="pdf2image or pytesseract not installed on server")

    result = {"pages": []}
    # render all pages to images (beware memory on large PDFs)
    images = convert_from_path(file_path, dpi=dpi)
    for pindex, image in enumerate(images):
        width_px, height_px = image.size
        text = None
        words = []
        try:
            ocr_data = pytesseract.image_to_data(image, output_type=Output.DICT)
            n_boxes = len(ocr_data.get("level", []))
            for i in range(n_boxes):
                conf = int(ocr_data["conf"][i]) if ocr_data["conf"][i] != "-1" else -1
                txt = ocr_data["text"][i].strip()
                if txt == "":
                    continue
                left = int(ocr_data["left"][i])
                top = int(ocr_data["top"][i])
                w = int(ocr_data["width"][i])
                h = int(ocr_data["height"][i])
                bbox = [left, top, left + w, top + h]
                words.append({"text": txt, "bbox": bbox, "conf": conf})
            # also whole-text
            text = pytesseract.image_to_string(image)
        except Exception:
            pass

        result["pages"].append(
            {
                "page_number": pindex,
                "width_px": width_px,
                "height_px": height_px,
                "text": text or "",
                "words": words,
                "tables": [],
            }
        )

    return result


@app.post("/extract")
def extract(req: ExtractRequest):
    """
    Run one or more extraction pipelines on an uploaded PDF.
    Returns JSON with per-model outputs.
    """
    file_path = _safe_file_path(req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    supported_models = {"pdfplumber", "tesseract"}
    chosen = [m for m in req.models if m in supported_models]
    if not chosen:
        raise HTTPException(status_code=400, detail=f"No valid models chosen. Supported: {list(supported_models)}")

    response = {"filename": req.filename, "models": {}, "summary_markdown": ""}

    # For each chosen model, run extraction
    for m in chosen:
        try:
            if m == "pdfplumber":
                response["models"]["pdfplumber"] = extract_with_pdfplumber(file_path, dpi=PREVIEW_DPI)
            elif m == "tesseract":
                response["models"]["tesseract"] = extract_with_tesseract(file_path, dpi=PREVIEW_DPI)
        except HTTPException as e:
            # re-raise dependency errors (e.g., library not installed)
            raise e
        except Exception as e:
            log.exception("Extraction error for model %s", m)
            response["models"][m] = {"error": str(e)}

    # Produce a simple combined markdown: concatenate first page text from each model (quick fallback)
    md_parts = []
    for m in chosen:
        model_out = response["models"].get(m, {})
        if isinstance(model_out, dict):
            pages = model_out.get("pages", [])
            if pages:
                md_parts.append(f"## {m} - page 0 text\n\n```\n{pages[0].get('text','')[:2000]}\n```\n")
    response["summary_markdown"] = "\n\n".join(md_parts)

    # Save result to disk for later retrieval
    rid = uuid.uuid4().hex
    outpath = os.path.join(RESULTS_DIR, f"{rid}_{req.filename}.json")
    try:
        import json

        with open(outpath, "w", encoding="utf-8") as fh:
            json.dump(response, fh, ensure_ascii=False, indent=2)
        response["result_file"] = os.path.basename(outpath)
    except Exception:
        log.exception("Failed to save result file")

    return response


@app.get("/preview/{filename}/{page_index}")
def preview_image(filename: str, page_index: int):
    """
    Return a PNG preview of a specified PDF page (0-indexed). Uses pdf2image.
    """
    file_path = _safe_file_path(filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        image_path = _save_preview_png(file_path, page_index, dpi=PREVIEW_DPI)
    except HTTPException as e:
        raise e
    except Exception as e:
        log.exception("Preview generation failed")
        raise HTTPException(status_code=500, detail="Preview generation failed")

    return FileResponse(image_path, media_type="image/png")


@app.get("/file/{filename}")
def serve_file(filename: str):
    fp = _safe_file_path(filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(fp, media_type="application/pdf")


@app.get("/models")
def available_models():
    return {"supported_models": ["pdfplumber", "tesseract"]}


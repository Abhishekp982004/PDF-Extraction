# PDF Extraction Playground

A full-stack playground for PDF text and table extraction, featuring a Next.js frontend and a FastAPI backend with OCR support.

## Setup

### Backend (FastAPI)
1. Install requirements:
    ```
    pip install -r requirements.txt
    ```
2. Start the backend server:
    ```
    uvicorn main:app --reload
    ```

### Frontend (Next.js)
1. Install dependencies:
    ```
    npm install
    ```
2. Start the frontend:
    ```
    npm run dev
    ```
3. Open [http://localhost:3000](http://localhost:3000) to access the app.

## Architecture

- **Frontend:** Next.js (React, TailwindCSS, React-Markdown) for UI, file upload, and displaying extracted content.
- **Backend:** FastAPI handles PDF uploads, text/table extraction using pdfplumber and OCR with pytesseract, and preview endpoints.
- **Modal support:** Modal app for scalable deployment, uses persistent volume for upload/preview/result storage.

## Model Descriptions and Capabilities

- **pdfplumber:** Extracts text, word bounding boxes, and tables (as CSV-like rows) from digital PDFs.
- **pytesseract:** Performs OCR on scanned/image-based PDFs; returns extracted text, word positions, and confidence per word.
- Both can be run individually or results combined. Extraction supports JSON, Markdown previews for easy integration and review.

## Deployment

### Local
- Start backend (FastAPI/Uvicorn) and frontend (Next.js) as above.

### Cloud
- Deploy frontend on Vercel (recommended).
- Deploy backend as a Modal app:
    ```
    modal deploy modal_app.py
    ```
- Make sure to configure CORS settings to allow the frontend to communicate with the backend API.

## Screenshots and GIFs

To demonstrate features:
- Capture screenshots or GIFs during file upload, extraction, preview, and result display.
- Store them in `/public` or `/docs`
- Embed in markdown:
    ```
    
    See all screenshots and demo GIFs in [trial.pdf](./trial.pdf)
    ```

## Example Usage

- Upload a PDF (digital or scanned).
- Preview the uploaded PDF.
- Extract and view as structured text, tables, and OCR results.

---

Built with FastAPI, Next.js, TailwindCSS, pdfplumber, and pytesseract.

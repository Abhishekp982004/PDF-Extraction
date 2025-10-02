// frontend/pages/index.tsx
"use client";

import React, { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");
  const [selectedModels, setSelectedModels] = useState<{ [k: string]: boolean }>({
    pdfplumber: true,
    tesseract: false,
  });
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const [pageWidth, setPageWidth] = useState(800);
  const [pageHeight, setPageHeight] = useState(1000);

  const upload = async () => {
    if (!file) {
      setMessage("Please choose a file.");
      return;
    }
    setMessage("Uploading...");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setUploadedFilename(data.filename);
      setMessage("Upload complete.");
    } catch (err) {
      setMessage("Upload failed.");
      console.error(err);
    }
  };

  const extract = async () => {
    if (!uploadedFilename) {
      setMessage("Upload a file first.");
      return;
    }
    setLoading(true);
    setMessage("Extracting...");
    try {
      const models = Object.keys(selectedModels).filter((k) => selectedModels[k]);
      const res = await fetch(`${API_BASE}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: uploadedFilename, models }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Extract failed: ${txt}`);
      }
      const data = await res.json();
      setResult(data);
      setMessage("Extraction complete.");
      // set page dims if pdfplumber model present
      const mp = data.models?.pdfplumber?.pages?.[0];
      if (mp) {
        setPageWidth(mp.width_px || mp.width_pts || 800);
        setPageHeight(mp.height_px || mp.height_pts || 1000);
      }
    } catch (err) {
      console.error(err);
      setMessage("Extraction failed. See console for details.");
    } finally {
      setLoading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!result) return;
    const md = result.summary_markdown || "";
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (uploadedFilename || "extracted") + ".md";
    a.click();
    URL.revokeObjectURL(url);
  };

  // overlay boxes for first page and first model (pdfplumber preferred)
  const boxes = (() => {
    if (!result) return [];
    const model = result.models?.pdfplumber || result.models?.tesseract;
    if (!model) return [];
    const page = model.pages?.[0];
    if (!page) return [];
    // page.words are in pixel coordinates (backend provides width_px/height_px)
    return { words: page.words || [], width_px: page.width_px || page.width_pts, height_px: page.height_px || page.height_pts };
  })();

  // compute scale when rendering preview image
  const [imgDisplayWidth, setImgDisplayWidth] = useState(600);
  useEffect(() => {
    // keep container responsive: set display width based on container size if possible
    if (previewRef.current) {
      const w = Math.min(800, Math.max(300, previewRef.current.clientWidth || 600));
      setImgDisplayWidth(w);
    }
  }, [previewRef.current, uploadedFilename, result]);

  const renderBoxes = () => {
    if (!boxes || !boxes.words) return null;
    const scale = imgDisplayWidth / (boxes.width_px || pageWidth || 800);
    return boxes.words.map((w: any, i: number) => {
      const [x0, y0, x1, y1] = w.bbox;
      const left = x0 * scale;
      const top = y0 * scale;
      const width = (x1 - x0) * scale;
      const height = (y1 - y0) * scale;
      return (
        <div
          key={i}
          style={{
            position: "absolute",
            left,
            top,
            width,
            height,
            border: "2px solid rgba(0,200,128,0.7)",
            background: "rgba(0,200,128,0.08)",
            pointerEvents: "none",
            boxSizing: "border-box",
          }}
          title={w.text}
        />
      );
    });
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white flex flex-col items-center p-8">
      <h1 className="text-3xl font-bold mb-4">PDF Extraction Playground</h1>

      <div className="mb-6 flex gap-4">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:bg-purple-600 file:text-white"
        />
        <button onClick={upload} className="px-4 py-2 bg-purple-600 rounded" disabled={!file}>
          Upload
        </button>
        <span className="self-center text-sm text-gray-300">{uploadedFilename ? `Uploaded: ${uploadedFilename}` : ""}</span>
      </div>

      <div className="mb-6 flex gap-4 items-center">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={selectedModels.pdfplumber} onChange={() => setSelectedModels((s) => ({ ...s, pdfplumber: !s.pdfplumber }))} />
          pdfplumber
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={selectedModels.tesseract} onChange={() => setSelectedModels((s) => ({ ...s, tesseract: !s.tesseract }))} />
          tesseract
        </label>

        <button onClick={extract} className="px-4 py-2 bg-green-600 rounded" disabled={!uploadedFilename || loading}>
          {loading ? "Extracting..." : "Run Extraction"}
        </button>
        <button onClick={downloadMarkdown} className="px-4 py-2 bg-blue-600 rounded" disabled={!result}>
          Download Markdown
        </button>
      </div>

      <div className="w-full max-w-6xl grid grid-cols-2 gap-6">
        {/* Left: preview with overlay */}
        <div className="bg-gray-800 p-4 rounded" ref={previewRef}>
          <div style={{ position: "relative", width: imgDisplayWidth }}>
            {uploadedFilename ? (
              <img
                src={`${API_BASE}/preview/${uploadedFilename}/0`}
                width={imgDisplayWidth}
                alt="preview"
                style={{ display: "block", maxWidth: "100%" }}
                onLoad={(e) => {
                  const w = (e.target as HTMLImageElement).naturalWidth;
                  const h = (e.target as HTMLImageElement).naturalHeight;
                  setImgDisplayWidth(Math.min(900, w));
                }}
              />
            ) : (
              <div className="text-gray-400">Upload a PDF and run extraction to see preview + annotations</div>
            )}

            {/* overlay boxes */}
            <div style={{ position: "absolute", left: 0, top: 0 }}>{renderBoxes()}</div>
          </div>
        </div>

        {/* Right: markdown / JSON result */}
        <div className="bg-gray-800 p-4 rounded overflow-auto max-h-[70vh]">
          <h2 className="text-xl font-semibold mb-2">Extraction Result</h2>
          {result ? (
            <>
              <div className="mb-2 text-sm text-gray-300">Summary (auto):</div>
              <div className="prose prose-invert bg-gray-900 p-4 rounded">
                <ReactMarkdown>{result.summary_markdown || "No summary"}</ReactMarkdown>
              </div>

              <details className="mt-4">
                <summary className="cursor-pointer">Full JSON</summary>
                <pre className="text-xs mt-2 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
              </details>
            </>
          ) : (
            <div className="text-gray-400">No results yet</div>
          )}
        </div>
      </div>

      <div className="mt-6 text-sm text-gray-400">{message}</div>
    </main>
  );
}

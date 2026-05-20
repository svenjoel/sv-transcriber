"use client";

import { useState } from "react";
import { uploadMedia, startJob } from "../lib/api";

export default function UploadDropzone() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>("");

  async function onGo() {
    if (!file) return;

    try {
      setStatus("Uploading...");
      const up = await uploadMedia(file);

      console.log("Upload response:", up); // ✅ debug

      const mediaId = up.id ?? up.media_id; // ✅ support both formats

      if (!mediaId) {
        throw new Error("Upload response missing id/media_id");
      }

      setStatus("Starting job...");
      const job = await startJob(mediaId);

      console.log("Job response:", job); // ✅ debug

      setStatus(`Job started (${job.id}). Redirecting...`);

      // ✅ small delay so user sees feedback
      setTimeout(() => {
        window.location.href = `/transcripts/${mediaId}`;
      }, 500);

    } catch (err: any) {
      console.error(err);
      setStatus(`❌ Error: ${err.message || "Something went wrong"}`);
    }
  }

  return (
    <div style={{
      background: "white",
      padding: 24,
      borderRadius: 16,
      boxShadow: "0 6px 18px rgba(0,0,0,.08)"
    }}>
      <h2 style={{ marginTop: 0 }}>Upload Swedish audio/video</h2>
      <p style={{ color: "#666" }}>
        MP3/WAV/M4A/MP4 supported (FFmpeg will normalize).
      </p>

      <input
        type="file"
        accept="audio/*,video/*"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />

      <div style={{ height: 12 }} />

      <button
        disabled={!file}
        onClick={onGo}
        style={{
          padding: "10px 14px",
          borderRadius: 12,
          border: "none",
          background: "#2563eb",
          color: "white",
          cursor: file ? "pointer" : "not-allowed"
        }}
      >
        Upload & Transcribe
      </button>

      {status && (
        <p style={{ marginTop: 12 }}>
          {status}
        </p>
      )}
    </div>
  );
}
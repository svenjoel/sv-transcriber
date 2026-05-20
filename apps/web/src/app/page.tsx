import UploadDropzone from "../components/UploadDropzone";

export default function Page() {
  return (
    <main style={{ minHeight: "100vh", background: "#f9fafb", padding: 32 }}>
      <div style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
        <header>
          <h1 style={{ margin: 0 }}>sv-transcriber</h1>
          <p style={{ margin: "6px 0 0", color: "#666" }}>Upload → Swedish transcription → diarization → edit speakers</p>
        </header>
        <UploadDropzone />
      </div>
    </main>
  );
}

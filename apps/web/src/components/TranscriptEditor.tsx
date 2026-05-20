"use client";

import { useMemo, useState } from "react";
import { renameSpeaker } from "../lib/api";

export default function TranscriptEditor({ transcript }: { transcript: any }) {
  const [filter, setFilter] = useState<string>("");
  const segments = transcript?.segments || [];

  const speakers = useMemo(() => {
    const set = new Set<string>();
    for (const s of segments) set.add(s.speaker_name || s.speaker);
    return Array.from(set).sort();
  }, [segments]);

  const shown = useMemo(() => {
    if (!filter) return segments;
    return segments.filter((s: any) => (s.speaker_name || s.speaker) === filter);
  }, [segments, filter]);

  async function onRename(oldLabel: string) {
    const name = prompt(`Rename ${oldLabel} to:`);
    if (!name) return;
    await renameSpeaker(transcript.transcript_id, oldLabel, name);
    window.location.reload();
  }

  return (
    <div style={{ background: "white", padding: 24, borderRadius: 16, boxShadow: "0 6px 18px rgba(0,0,0,.08)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>Transcript</h2>
          <p style={{ margin: "6px 0 0", color: "#666" }}>Filter by speaker and rename labels.</p>
        </div>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ padding: "10px 12px", borderRadius: 12 }}>
          <option value="">All speakers</option>
          {speakers.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div style={{ height: 12 }} />

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {shown.map((s: any, idx: number) => (
          <div key={idx} style={{ border: "1px solid #e5e7eb", borderRadius: 16, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {(s.speaker_name || s.speaker)}
                <span style={{ color: "#6b7280", fontWeight: 400, marginLeft: 8 }}>
                  [{s.start.toFixed(1)}–{s.end.toFixed(1)}]
                </span>
              </div>
              <button onClick={() => onRename(s.speaker)} style={{ padding: "6px 10px", borderRadius: 12, border: "1px solid #d1d5db", background: "white" }}>
                Rename
              </button>
            </div>
            <div style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{s.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

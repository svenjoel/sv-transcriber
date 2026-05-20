'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';

const API_BASE = 'http://127.0.0.1:8000';
const colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea'];

type SpeakerMap = Record<string, string>;

function confPill(conf?: number | null) {
  if (typeof conf !== 'number') return null;
  return (
    <span style={{ marginLeft: 8, fontSize: 11, color: '#666' }}>
      ({conf}%)
    </span>
  );
}

function sanitizeForSave(v: string) {
  return (v || '').replace(/\s+/g, ' ').trim();
}

function formatTime(t: number) {
  if (!Number.isFinite(t)) return '0:00';
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function TranscriptPage() {
  const { id } = useParams();

  const [data, setData] = useState<any>(null);
  const [speakerNames, setSpeakerNames] = useState<SpeakerMap>({});
  const [status, setStatus] = useState('');

  // audio
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);

  // Play-only-this-segment support
  const segmentEndRef = useRef<number | null>(null);
  const [isSegmentMode, setIsSegmentMode] = useState(false);

  // auto-scroll active segment
  const activeSegRef = useRef<HTMLDivElement | null>(null);
  const lastAutoScrollAt = useRef<number>(0);

  async function load() {
    const res = await fetch(`${API_BASE}/media/${id}`, { cache: 'no-store' });
    const json = await res.json();
    setData(json);
    setSpeakerNames(json.speaker_map || {});
  }

  useEffect(() => {
    if (!id) return;
    load();
  }, [id]);

  // hooks MUST be before any early return
  const speakerLabels = useMemo<string[]>(() => {
    if (!data?.segments) return [];
    return Array.from(
      new Set(
        data.segments.map(
          (s: any) => (s.original_speaker || s.speaker || 'Unknown') as string
        )
      )
    );
  }, [data]);

  const grouped = useMemo<any[]>(() => {
    if (!data?.segments) return [];
    const groups: any[] = [];

    for (const seg of data.segments) {
      const original = seg.original_speaker || seg.speaker || 'Unknown';
      const last = groups[groups.length - 1];

      if (last && last.original === original) {
        last.text += ' ' + (seg.text || '');
        last.end = seg.end;

        if (typeof seg.confidence === 'number') {
          last._confSum = (last._confSum || 0) + seg.confidence;
          last._confCount = (last._confCount || 0) + 1;
          last.confidence = Math.round(last._confSum / last._confCount);
        }
      } else {
        groups.push({
          original,
          start: seg.start,
          end: seg.end,
          text: seg.text || '',
          confidence: typeof seg.confidence === 'number' ? seg.confidence : null,
          _confSum: typeof seg.confidence === 'number' ? seg.confidence : 0,
          _confCount: typeof seg.confidence === 'number' ? 1 : 0,
          speaker: seg.speaker,
        });
      }
    }

    return groups.map(({ _confSum, _confCount, ...rest }) => rest);
  }, [data]);

  const managerLabels = useMemo<string[]>(() => {
    const metaKeys: string[] = data?.speaker_map_auto_meta
      ? Object.keys(data.speaker_map_auto_meta)
      : [];
    if (metaKeys.length) return metaKeys;
    return speakerLabels;
  }, [data, speakerLabels]);

  async function saveNames(next?: SpeakerMap) {
    const map = next ?? speakerNames;
    const payload: SpeakerMap = {};

    for (const [k, v] of Object.entries(map)) {
      const clean = sanitizeForSave(v);
      if (clean) payload[k] = clean;
    }

    setStatus('Saving...');
    const res = await fetch(`${API_BASE}/media/${id}/speaker-map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      setStatus(`❌ ${text || 'Save failed'}`);
      return;
    }

    setStatus('✅ Saved');
    await load();
  }

  const audioUrl = `${API_BASE}/media/${id}/audio`;

  /**
   * Robust seek (works with your Range-enabled backend)
   * - attaches seeked listener BEFORE playing
   * - fallback play after a short delay (browser edge case)
   */
  function seekTo(seconds: number, autoplay = true) {
    const a = audioRef.current;
    if (!a || !Number.isFinite(seconds)) return;

    const target = Math.max(0, seconds);

    a.pause();

    const tryPlay = () => {
      if (!autoplay) return;
      a.play().catch(() => {});
    };

    if (autoplay) {
      a.addEventListener('seeked', tryPlay, { once: true });
    }

    try {
      a.currentTime = target;
    } catch {
      // ignore
    }

    if (autoplay) {
      window.setTimeout(() => {
        if (a.paused) a.play().catch(() => {});
      }, 120);
    }
  }

  // ✅ Play only a segment (auto-stop at end)
  function playSegment(start: number, end: number) {
    segmentEndRef.current = end;
    setIsSegmentMode(true);
    seekTo(start, true);
  }

  // normal play clears segment limit
  function togglePlay() {
    const a = audioRef.current;
    if (!a) return;

    // leaving segment mode when using main controls
    segmentEndRef.current = null;
    setIsSegmentMode(false);

    if (a.paused) a.play().catch(() => {});
    else a.pause();
  }

  function onTimelineClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!duration) return;

    // exit segment mode
    segmentEndRef.current = null;
    setIsSegmentMode(false);

    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const t = Math.max(0, Math.min(duration, ratio * duration));
    seekTo(t, true);
  }

  // ✅ BONUS: auto-scroll to active segment (throttled)
  useEffect(() => {
    if (!playing) return;
    const now = Date.now();
    if (now - lastAutoScrollAt.current < 600) return;
    if (activeSegRef.current) {
      activeSegRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      lastAutoScrollAt.current = now;
    }
  }, [currentTime, playing]);

  // -----------------------
  // Keyboard shortcuts
  // -----------------------
  const isTypingInInput = () => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return false;
    const tag = el.tagName?.toUpperCase();
    return tag === 'INPUT' || tag === 'TEXTAREA' || (el as any).isContentEditable;
  };

  const clearSelectionMode = () => {
    segmentEndRef.current = null;
    setIsSegmentMode(false);
  };

  const skipBy = (deltaSeconds: number) => {
    const a = audioRef.current;
    if (!a) return;
    clearSelectionMode();
    const max = (Number.isFinite(duration) && duration > 0) ? duration : (a.duration || Infinity);
    const next = Math.max(0, Math.min(max, a.currentTime + deltaSeconds));
    seekTo(next, true);
  };

  const jumpSegment = (direction: -1 | 1) => {
    const a = audioRef.current;
    if (!a || !grouped?.length) return;
    clearSelectionMode();

    const t = a.currentTime;

    // Find segment index where current time falls within [start, end)
    let idx = grouped.findIndex((s: any) => typeof s.start === 'number' && typeof s.end === 'number' && t >= s.start && t < s.end);

    if (idx === -1) {
      // If not inside any segment, choose nearest boundary
      if (direction === 1) {
        idx = grouped.findIndex((s: any) => typeof s.start === 'number' && s.start > t) - 1;
      } else {
        idx = grouped.findIndex((s: any) => typeof s.start === 'number' && s.start >= t);
        if (idx === -1) idx = grouped.length;
      }
    }

    const nextIdx = Math.max(0, Math.min(grouped.length - 1, idx + direction));
    const nextStart = grouped[nextIdx]?.start;
    if (typeof nextStart === 'number') seekTo(nextStart, true);
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't steal keys while typing speaker names
      if (isTypingInInput()) return;

      // Space: play/pause (do NOT clear selection mode here)
      if (e.code === 'Space') {
        e.preventDefault();
        const a = audioRef.current;
        if (!a) return;
        if (a.paused) a.play().catch(() => {});
        else a.pause();
        return;
      }

      // Arrow left/right: skip
      if (e.code === 'ArrowLeft' || e.code === 'ArrowRight') {
        e.preventDefault();
        const step = e.shiftKey ? 15 : 5;
        skipBy(e.code === 'ArrowLeft' ? -step : step);
        return;
      }

      // Arrow up/down: jump segments
      if (e.code === 'ArrowUp' || e.code === 'ArrowDown') {
        e.preventDefault();
        jumpSegment(e.code === 'ArrowUp' ? -1 : 1);
        return;
      }
    };

    window.addEventListener('keydown', handler, { passive: false } as any);
    return () => window.removeEventListener('keydown', handler as any);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grouped, duration]);

  if (!data) return <main style={{ padding: 24 }}>Loading…</main>;

  return (
    <main style={{ display: 'flex', height: '100vh' }}>
      {/* LEFT: speaker manager */}
      <aside
        style={{
          width: 320,
          borderRight: '1px solid #eee',
          padding: 16,
          overflowY: 'auto',
          background: '#fafafa',
        }}
      >
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 800, fontSize: 14 }}>Speaker manager</div>
          <div style={{ fontSize: 12, color: '#666' }}>
            Rename speakers for this transcript. Saves on blur.
          </div>
        </div>

        <details style={{ marginBottom: 14 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12, color: '#2563eb', fontWeight: 700 }}>
            Keyboard shortcuts
          </summary>
          <div style={{ fontSize: 12, color: '#444', marginTop: 8, lineHeight: 1.5 }}>
            <div><b>Space</b> — Play/Pause</div>
            <div><b>← / →</b> — Skip 5s</div>
            <div><b>Shift + ← / →</b> — Skip 15s</div>
            <div><b>↑ / ↓</b> — Previous/Next segment</div>
            <div style={{ marginTop: 6, color: '#666' }}>
              Tip: Click a bubble to play only that segment.
            </div>
          </div>
        </details>

        {managerLabels.map((label: string) => {
          const meta = data?.speaker_map_auto_meta?.[label];
          const conf = typeof meta?.confidence === 'number' ? meta.confidence : null;
          const suggested = (data?.speaker_map_auto?.[label] || meta?.best_name || '').trim();
          const accepted = (data?.speaker_map_auto_accepted?.[label] || '').trim();

          const current =
            speakerNames[label] !== undefined ? speakerNames[label] : (accepted || suggested || '');

          return (
            <div
              key={label}
              style={{
                border: '1px solid #eee',
                background: 'white',
                borderRadius: 10,
                padding: 10,
                marginBottom: 10,
              }}
            >
              <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>
                <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
                  {label}
                </span>
                {confPill(conf)}
              </div>

              <input
                value={current}
                placeholder="Name…"
                onChange={(e) =>
                  setSpeakerNames((prev) => ({
                    ...prev,
                    [label]: e.target.value, // spaces allowed while typing
                  }))
                }
                onBlur={() => saveNames()}
                style={{
                  width: '100%',
                  padding: 8,
                  borderRadius: 8,
                  border: '1px solid #ddd',
                  outline: 'none',
                }}
              />

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  onClick={() => {
                    if (!suggested) return;
                    const next = { ...speakerNames, [label]: suggested };
                    setSpeakerNames(next);
                    saveNames(next);
                  }}
                  style={{
                    flex: 1,
                    padding: '6px 10px',
                    borderRadius: 8,
                    border: '1px solid #ddd',
                    background: suggested ? 'white' : '#f3f4f6',
                    cursor: suggested ? 'pointer' : 'not-allowed',
                    fontWeight: 700,
                    fontSize: 12,
                  }}
                  title={suggested ? 'Accept suggestion' : 'No suggestion'}
                >
                  Accept
                </button>

                <button
                  onClick={() => {
                    const next = { ...speakerNames };
                    delete next[label];
                    setSpeakerNames(next);
                    saveNames(next);
                  }}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 8,
                    border: '1px solid #ddd',
                    background: 'white',
                    cursor: 'pointer',
                    fontWeight: 700,
                    fontSize: 12,
                  }}
                  title="Clear manual override"
                >
                  Clear
                </button>
              </div>

              {accepted && (
                <div style={{ marginTop: 6, fontSize: 12, color: '#166534' }}>
                  Auto-accepted: <b>{accepted}</b>
                </div>
              )}
              {!accepted && suggested && (
                <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
                  Suggestion: <b>{suggested}</b>
                </div>
              )}
            </div>
          );
        })}

        <div style={{ marginTop: 10, fontSize: 12, color: '#666' }}>{status}</div>
      </aside>

      {/* RIGHT: transcript + audio */}
      <section style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
        <h1 style={{ margin: 0 }}>Transcript</h1>
        <div style={{ color: '#666', marginTop: 6, marginBottom: 16 }}>
          {data.filename}
        </div>

        {/* Hidden native audio UI */}
        <audio
          ref={audioRef}
          src={audioUrl}
          preload="metadata"
          onLoadedMetadata={(e) => {
            const a = e.currentTarget;
            setDuration(a.duration || 0);
            setCurrentTime(a.currentTime || 0);
          }}
          onTimeUpdate={(e) => {
            const a = e.currentTarget;
            const t = a.currentTime || 0;
            setCurrentTime(t);

            // auto-stop if in selection mode
            const segEnd = segmentEndRef.current;
            if (segEnd != null && t >= segEnd) {
              a.pause();
              segmentEndRef.current = null;
              setIsSegmentMode(false);
            }
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          style={{ display: 'none' }}
        />

        {/* Single custom player */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            marginBottom: 20,
            marginTop: 10,
          }}
        >
          <button
            onClick={togglePlay}
            style={{
              fontSize: 18,
              padding: '6px 10px',
              borderRadius: 10,
              border: '1px solid #ddd',
              background: 'white',
              cursor: 'pointer',
              fontWeight: 800,
              minWidth: 44,
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
            }}
            title={playing ? 'Pause' : 'Play'}
          >
            {playing ? '⏸' : '▶'}
          </button>

          <div
            onClick={onTimelineClick}
            style={{
              flex: 1,
              height: 10,
              background: '#e5e7eb',
              borderRadius: 999,
              cursor: 'pointer',
              position: 'relative',
              transition: 'background 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#d1d5db')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#e5e7eb')}
            title="Click to seek"
          >
            <div
              style={{
                height: 10,
                background: '#2563eb',
                width: duration ? `${(currentTime / duration) * 100}%` : '0%',
                borderRadius: 999,
                transition: 'width 0.15s linear',
              }}
            />
          </div>

          <div
            style={{
              fontSize: 12,
              color: '#666',
              minWidth: 90,
              textAlign: 'right',
              fontVariantNumeric: 'tabular-nums',
            }}
            title="Time"
          >
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          {isSegmentMode && (
            <div
              style={{
                fontSize: 12,
                color: '#2563eb',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                padding: '4px 8px',
                borderRadius: 999,
              }}
              title="Playing only selected segment"
            >
              🎧 Playing selection
            </div>
          )}
        </div>

        <div style={{ fontSize: 12, color: '#666', marginBottom: 16 }}>
          Shortcuts: <b>Space</b> play/pause • <b>←/→</b> ±5s • <b>Shift+←/→</b> ±15s • <b>↑/↓</b> prev/next segment • Click a bubble to play only that segment.
        </div>

        {/* Chat transcript */}
        {grouped.map((seg: any, i: number) => {
          const original = seg.original;
          const confidence = seg.confidence;

          const labelIndex = speakerLabels.indexOf(original);
          const stableIndex = labelIndex >= 0 ? labelIndex : i;

          const color = colors[stableIndex % colors.length];
          const isLeft = stableIndex % 2 === 0;

          const display =
            (speakerNames[original] || '').trim() ||
            seg.speaker ||
            original;

          const active = currentTime >= seg.start && currentTime <= seg.end;

          return (
            <div
              key={i}
              ref={active ? activeSegRef : null}
              style={{
                display: 'flex',
                justifyContent: isLeft ? 'flex-start' : 'flex-end',
                marginBottom: 16,
              }}
            >
              <div style={{ maxWidth: '70%' }}>
                <div style={{ fontSize: 12, color: '#666' }}>
                  <span style={{ fontWeight: 800, color }}>{display}</span>
                  {confPill(confidence)}
                </div>

                <div
                  onClick={() => playSegment(seg.start, seg.end)}
                  style={{
                    background: active ? '#dbeafe' : isLeft ? '#f3f4f6' : '#2563eb',
                    color: isLeft ? '#111' : 'white',
                    padding: 12,
                    borderRadius: 12,
                    marginTop: 4,
                    cursor: 'pointer',
                    boxShadow: active ? '0 0 0 2px rgba(37,99,235,0.25)' : 'none',
                  }}
                  title={`Play only this segment (${Number(seg.start).toFixed(1)}–${Number(seg.end).toFixed(1)}s)`}
                >
                  {seg.text}
                </div>

                <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                  {seg.start?.toFixed(1)}–{seg.end?.toFixed(1)}s
                </div>
              </div>
            </div>
          );
        })}
      </section>
    </main>
  );
}
``
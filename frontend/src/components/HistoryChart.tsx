"use client";

import type { HistoryPoint } from "@/lib/api";

const COLORS: Record<string, string> = {
  google: "#2563eb",
  tripadvisor: "#059669",
};
const FALLBACK = ["#d97706", "#7c3aed", "#db2777"];

const W = 640;
const H = 220;
const PAD = { top: 12, right: 16, bottom: 28, left: 32 };

/** Score (0-10) per source over time, one line per source. */
export function HistoryChart({ points, labels }: { points: HistoryPoint[]; labels: Record<string, string> }) {
  const valid = points.filter((p) => p.score_10 != null);
  const days = [...new Set(valid.map((p) => p.day))].sort();
  const sources = [...new Set(valid.map((p) => p.source))];
  const t0 = Date.parse(days[0]);
  const t1 = Date.parse(days[days.length - 1]);
  const span = Math.max(t1 - t0, 1);

  const x = (day: string) => PAD.left + ((Date.parse(day) - t0) / span) * (W - PAD.left - PAD.right);
  const y = (score: number) => PAD.top + (1 - score / 10) * (H - PAD.top - PAD.bottom);
  const fmt = (day: string) => `${day.slice(8, 10)}.${day.slice(5, 7)}.${day.slice(0, 4)}`;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {[0, 2.5, 5, 7.5, 10].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="#e2e8f0" />
            <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#64748b">
              {v}
            </text>
          </g>
        ))}
        {[days[0], days[days.length - 1]].map((d, i) => (
          <text
            key={d + i}
            x={x(d)}
            y={H - 8}
            textAnchor={i === 0 ? "start" : "end"}
            fontSize="11"
            fill="#64748b"
          >
            {fmt(d)}
          </text>
        ))}
        {sources.map((src, i) => {
          const color = COLORS[src] ?? FALLBACK[i % FALLBACK.length];
          const pts = valid.filter((p) => p.source === src);
          return (
            <g key={src}>
              <polyline
                fill="none"
                stroke={color}
                strokeWidth="2"
                points={pts.map((p) => `${x(p.day)},${y(p.score_10!)}`).join(" ")}
              />
              {pts.map((p) => (
                <circle key={p.day} cx={x(p.day)} cy={y(p.score_10!)} r="3" fill={color}>
                  <title>{`${labels[src] ?? src} ${p.day}: ${p.score_10}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
        {sources.map((src, i) => (
          <span key={src} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-4 rounded"
              style={{ background: COLORS[src] ?? FALLBACK[i % FALLBACK.length] }}
            />
            {labels[src] ?? src}
          </span>
        ))}
      </div>
    </div>
  );
}

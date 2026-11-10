"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { LangSwitch } from "@/components/LangSwitch";
import { loadReport, type Lang, type Report } from "@/lib/api";
import { MAX_COMPARE } from "@/lib/compare";
import { parseLang, t, type Strings } from "@/lib/i18n";

type Row = { label: string; values: (number | null)[] };

/** One table row per measure; the best hotel in each row is highlighted. */
function buildRows(reports: Report[], s: Strings): Row[] {
  const rows: Row[] = [{ label: s.overall, values: reports.map((r) => r.overall_score_10) }];

  const sources = new Map<string, string>();
  reports.forEach((r) => r.sources.forEach((src) => sources.set(src.source, src.source_label)));
  sources.forEach((label, key) =>
    rows.push({
      label: s.sourceRow(label),
      values: reports.map((r) => r.sources.find((src) => src.source === key)?.score_10 ?? null),
    }),
  );

  const topics = new Set<string>();
  reports.forEach((r) => r.topics.forEach((tp) => topics.add(tp.topic)));
  topics.forEach((topic) =>
    rows.push({
      label: s.topicNames[topic as keyof Strings["topicNames"]] ?? topic,
      values: reports.map((r) => r.topics.find((tp) => tp.topic === topic)?.score_10 ?? null),
    }),
  );
  return rows;
}

function Compare() {
  const router = useRouter();
  const params = useSearchParams();
  const lang = parseLang(params.get("lang"));
  const s = t(lang);
  const idsParam = params.get("ids") ?? "";
  const ids = idsParam
    .split(",")
    .map((x) => decodeURIComponent(x))
    .filter(Boolean)
    .slice(0, MAX_COMPARE);

  const [reports, setReports] = useState<(Report | null)[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hotelIds = idsParam
      .split(",")
      .map((x) => decodeURIComponent(x))
      .filter(Boolean)
      .slice(0, MAX_COMPARE);
    let cancelled = false;
    setReports(hotelIds.map(() => null));
    setError(null);
    hotelIds.forEach((id, i) =>
      loadReport(id, lang, () => cancelled)
        .then((r) => {
          if (r && !cancelled) setReports((prev) => prev.map((p, j) => (j === i ? r : p)));
        })
        .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err))),
    );
    return () => {
      cancelled = true;
    };
  }, [idsParam, lang]);

  const setLang = (l: Lang) => router.replace(`/compare?ids=${idsParam}&lang=${l}`);
  const ready = reports.length > 0 && reports.every(Boolean) ? (reports as Report[]) : null;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between gap-4 print:hidden">
        <Link href={`/?lang=${lang}`} className="text-sm text-slate-600 hover:text-slate-900">
          {s.back}
        </Link>
        <div className="flex items-center gap-2">
          {ready && (
            <button
              onClick={() => window.print()}
              className="rounded-lg bg-white px-3 py-1.5 text-sm shadow-sm ring-1 ring-slate-200 hover:ring-slate-400"
            >
              {s.downloadPdf}
            </button>
          )}
          <LangSwitch lang={lang} onChange={setLang} />
        </div>
      </div>

      <h1 className="mb-6 text-2xl font-semibold">{s.compareTitle}</h1>

      {ids.length < 2 && <p className="text-slate-600">{s.comparePickMore}</p>}
      {error && <p className="text-red-700">{s.error}: {error}</p>}
      {ids.length >= 2 && !ready && !error && (
        <p className="animate-pulse rounded-xl bg-white p-6 text-slate-600 ring-1 ring-slate-200">
          {s.compareLoading} ({reports.filter(Boolean).length}/{ids.length})
        </p>
      )}

      {ready && (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="w-44 p-3" />
                {ready.map((r) => (
                  <th key={r.hotel_id} className="p-3 text-left align-top font-semibold">
                    <Link
                      href={`/hotel/${encodeURIComponent(r.hotel_id)}?lang=${lang}`}
                      className="hover:underline"
                    >
                      {r.hotel_name}
                    </Link>
                    <div className="mt-0.5 text-xs font-normal text-slate-500">
                      {r.total_reviews.toLocaleString(lang)} {s.reviews}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {buildRows(ready, s).map((row, i) => {
                // Highlight the best only when at least two hotels have a value and they differ.
                const present = row.values.filter((v): v is number => v != null);
                const best =
                  present.length >= 2 && Math.max(...present) > Math.min(...present)
                    ? Math.max(...present)
                    : null;
                return (
                  <tr key={row.label} className={`border-b border-slate-100 ${i === 0 ? "text-base" : ""}`}>
                    <td className={`p-3 text-slate-600 ${i === 0 ? "font-semibold text-slate-900" : ""}`}>
                      {row.label}
                    </td>
                    {row.values.map((v, j) => (
                      <td
                        key={j}
                        className={`p-3 tabular-nums ${
                          v != null && v === best
                            ? "font-semibold text-emerald-700"
                            : ""
                        }`}
                      >
                        {v == null ? "–" : v.toFixed(1)}
                      </td>
                    ))}
                  </tr>
                );
              })}
              <tr className="border-b border-slate-100">
                <td className="p-3 text-slate-600">{s.trust}</td>
                {ready.map((r) => (
                  <td key={r.hotel_id} className="p-3">
                    {!r.trust ? (
                      "–"
                    ) : r.trust.level === "ok" ? (
                      <span className="text-emerald-700">✓</span>
                    ) : (
                      <span className="text-amber-700">⚠ {r.trust.flags.length}</span>
                    )}
                  </td>
                ))}
              </tr>
              {(["pros", "cons"] as const).map((kind) => (
                <tr key={kind} className="border-b border-slate-100 align-top last:border-0">
                  <td className="p-3 text-slate-600">{kind === "pros" ? s.topPros : s.topCons}</td>
                  {ready.map((r) => (
                    <td key={r.hotel_id} className="p-3">
                      <ul className="space-y-1">
                        {r[kind].slice(0, 3).map((p) => (
                          <li key={p.text} className={kind === "pros" ? "text-emerald-800" : "text-rose-800"}>
                            {kind === "pros" ? "+" : "−"} {p.text}
                          </li>
                        ))}
                      </ul>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Compare />
    </Suspense>
  );
}

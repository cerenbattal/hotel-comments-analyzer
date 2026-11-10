"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { HistoryChart } from "@/components/HistoryChart";
import { LangSwitch } from "@/components/LangSwitch";
import { api, loadReport, type AskAnswer, type HistoryPoint, type Lang, type Point, type Report } from "@/lib/api";
import { parseLang, t, type Strings } from "@/lib/i18n";

function scoreColor(score: number) {
  if (score >= 8) return "bg-emerald-600";
  if (score >= 6) return "bg-amber-500";
  return "bg-rose-600";
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`break-inside-avoid rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200 ${className}`}>
      <h2 className="mb-3 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Points({ points, s, tone }: { points: Point[]; s: Strings; tone: "pro" | "con" }) {
  return (
    <ul className="space-y-3">
      {points.map((p) => (
        <li key={p.text}>
          <div className="flex items-baseline justify-between gap-3">
            <span className={`font-medium ${tone === "pro" ? "text-emerald-800" : "text-rose-800"}`}>
              {tone === "pro" ? "+" : "−"} {p.text}
            </span>
            <span className="shrink-0 text-xs text-slate-500">
              {p.mentions} {s.mentions}
            </span>
          </div>
          {p.quotes.map((q) => (
            <p key={q} className="mt-1 border-l-2 border-slate-200 pl-3 text-sm text-slate-600 italic">
              “{q}”
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
}

function Ask({ hotelId, lang, s }: { hotelId: string; lang: Lang; s: Strings }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    if (question.trim().length < 3) return;
    setLoading(true);
    setError(null);
    try {
      setAnswer(await api.ask(hotelId, question.trim(), lang));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card title={s.ask} className="print:hidden">
      <form onSubmit={onAsk} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={s.askPlaceholder}
          maxLength={500}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-slate-900"
        />
        <button
          disabled={loading}
          className="rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
        >
          {loading ? s.asking : s.askButton}
        </button>
      </form>
      {error && <p className="mt-3 text-red-700">{s.error}: {error}</p>}
      {answer && (
        <div className="mt-4">
          <p>{answer.answer}</p>
          {answer.quotes.map((q) => (
            <p key={q} className="mt-2 border-l-2 border-slate-200 pl-3 text-sm text-slate-600 italic">
              “{q}”
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}

function HotelReport() {
  const { id } = useParams<{ id: string }>();
  const hotelId = decodeURIComponent(id);
  const router = useRouter();
  const params = useSearchParams();
  const lang = parseLang(params.get("lang"));
  const s = t(lang);

  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [history, setHistory] = useState<HistoryPoint[]>([]);

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setError(null);

    // Start the build (or get a fresh report), then poll until it finishes.
    async function load() {
      const r = await loadReport(hotelId, lang, () => cancelled);
      if (!r) return;
      setReport(r);
      setHistory(await api.history(hotelId));
    }
    load().catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)));
    return () => {
      cancelled = true;
    };
  }, [hotelId, lang]);

  const setLang = (l: Lang) => router.replace(`/hotel/${encodeURIComponent(hotelId)}?lang=${l}`);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between gap-4 print:hidden">
        <Link href={`/?lang=${lang}`} className="text-sm text-slate-600 hover:text-slate-900">
          {s.back}
        </Link>
        <div className="flex items-center gap-2">
          {report && (
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

      {error && <p className="text-red-700">{s.error}: {error}</p>}
      {!report && !error && (
        <p className="animate-pulse rounded-xl bg-white p-6 text-slate-600 ring-1 ring-slate-200">
          {s.loadingReport}
        </p>
      )}

      {report && (
        <div className="space-y-5">
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div>
              {report.hotel_id.startsWith("demo:") && (
                <span className="mb-2 inline-block rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-900">
                  {s.demo}
                </span>
              )}
              <h1 className="text-2xl font-semibold">{report.hotel_name}</h1>
              <p className="text-slate-600">{report.address}</p>
            </div>
            {report.overall_score_10 != null && (
              <div className="text-right">
                <div
                  className={`inline-block rounded-xl px-4 py-2 text-3xl font-bold text-white ${scoreColor(report.overall_score_10)}`}
                >
                  {report.overall_score_10.toFixed(1)}
                </div>
                <div className="mt-1 text-xs text-slate-500">{s.overall} / 10</div>
              </div>
            )}
          </header>

          {report.summary && (
            <Card title={s.summary}>
              <p className="leading-relaxed">{report.summary}</p>
              <p className="mt-3 text-xs text-slate-500">
                {s.analyzedNote(report.analyzed_reviews, report.total_reviews)}
              </p>
            </Card>
          )}

          <Card title={s.bySource}>
            <table className="w-full text-sm">
              <tbody>
                {report.sources.map((src) => (
                  <tr key={src.source} className="border-t border-slate-100 first:border-0">
                    <td className="py-2 font-medium">
                      {src.url ? (
                        <a href={src.url} target="_blank" rel="noreferrer" className="underline">
                          {src.source_label}
                        </a>
                      ) : (
                        src.source_label
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {src.rating ?? "–"} / {src.scale_max}
                    </td>
                    <td className="py-2 text-right font-semibold">{src.score_10?.toFixed(1) ?? "–"}</td>
                    <td className="py-2 text-right text-slate-500">
                      {src.review_count.toLocaleString(lang)} {s.reviews}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-slate-500">{s.overallNote}</p>
          </Card>

          <Card title={s.history}>
            {new Set(history.map((h) => h.day)).size >= 2 ? (
              <HistoryChart
                points={history}
                labels={Object.fromEntries(report.sources.map((src) => [src.source, src.source_label]))}
              />
            ) : (
              <p className="text-sm text-slate-600">{s.historyEmpty}</p>
            )}
          </Card>

          <div className="grid gap-5 md:grid-cols-2">
            <Card title={s.pros}>
              <Points points={report.pros} s={s} tone="pro" />
            </Card>
            <Card title={s.cons}>
              <Points points={report.cons} s={s} tone="con" />
            </Card>
          </div>

          {report.topics.length > 0 && (
            <Card title={s.topics}>
              <ul className="space-y-2">
                {report.topics.map((tp) => (
                  <li key={tp.topic} className="grid grid-cols-[8rem_1fr_3rem] items-center gap-3 text-sm">
                    <span>{s.topicNames[tp.topic as keyof Strings["topicNames"]] ?? tp.topic}</span>
                    <div className="h-2 rounded bg-slate-100">
                      <div
                        className={`h-2 rounded ${scoreColor(tp.score_10)}`}
                        style={{ width: `${tp.score_10 * 10}%` }}
                      />
                    </div>
                    <span className="text-right font-medium">{tp.score_10.toFixed(1)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Ask hotelId={hotelId} lang={lang} s={s} />
        </div>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <HotelReport />
    </Suspense>
  );
}

"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { LangSwitch } from "@/components/LangSwitch";
import { api, type HotelCandidate, type Lang } from "@/lib/api";
import { MAX_COMPARE, useCompareList } from "@/lib/compare";
import { errorText, numberLocale, parseLang, t } from "@/lib/i18n";

function Home() {
  const router = useRouter();
  const params = useSearchParams();
  const lang = parseLang(params.get("lang"));
  const s = t(lang);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HotelCandidate[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compare = useCompareList();
  const setLang = (l: Lang) => router.replace(`/?lang=${l}`);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await api.search(query.trim(), lang));
    } catch (err) {
      setError(errorText(err, t(lang)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-10 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{s.title}</h1>
        <LangSwitch lang={lang} onChange={setLang} />
      </div>
      <p className="mb-6 text-slate-600">{s.tagline}</p>

      <form onSubmit={onSearch} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={s.searchPlaceholder}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-4 py-3 outline-none focus:border-slate-900"
        />
        <button
          disabled={loading}
          className="rounded-lg bg-slate-900 px-5 py-3 font-medium text-white disabled:opacity-60"
        >
          {loading ? s.searching : s.search}
        </button>
      </form>

      {error && <p className="mt-4 text-red-700">{error}</p>}
      {results && results.length === 0 && <p className="mt-6 text-slate-600">{s.noResults}</p>}

      <ul className="mt-6 space-y-2">
        {results?.map((h) => (
          <li key={h.id} className="flex items-stretch gap-2">
            <Link
              href={`/hotel/${encodeURIComponent(h.id)}?lang=${lang}`}
              className="block min-w-0 flex-1 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200 hover:ring-slate-400"
            >
              <div className="font-medium">{h.name}</div>
              <div className="text-sm text-slate-600">{h.address}</div>
              {h.rating != null && (
                <div className="mt-1 text-sm text-slate-500">
                  ★ {h.rating} · {h.review_count?.toLocaleString(numberLocale(lang))} {s.reviews}
                </div>
              )}
            </Link>
            <button
              onClick={() => compare.toggle(h)}
              disabled={!compare.has(h.id) && compare.items.length >= MAX_COMPARE}
              title={s.compareMax}
              className={`shrink-0 rounded-lg px-3 text-sm ring-1 disabled:opacity-40 ${
                compare.has(h.id)
                  ? "bg-slate-900 text-white ring-slate-900"
                  : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-400"
              }`}
            >
              {compare.has(h.id) ? s.inCompare : s.addToCompare}
            </button>
          </li>
        ))}
      </ul>

      {compare.items.length > 0 && (
        <div className="sticky bottom-4 mt-8 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-900 p-4 text-white shadow-lg">
          <span className="min-w-0 text-sm">
            {compare.items.map((h) => h.name).join(" · ")}
          </span>
          <div className="flex shrink-0 gap-2">
            <button onClick={compare.clear} className="rounded-lg px-3 py-2 text-sm text-slate-300 hover:text-white">
              ✕
            </button>
            <Link
              href={`/compare?ids=${compare.items.map((h) => encodeURIComponent(h.id)).join(",")}&lang=${lang}`}
              aria-disabled={compare.items.length < 2}
              className={`rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-900 ${
                compare.items.length < 2 ? "pointer-events-none opacity-50" : ""
              }`}
            >
              {s.compare} ({compare.items.length})
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Home />
    </Suspense>
  );
}

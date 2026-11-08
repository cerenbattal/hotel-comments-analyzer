"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { LangSwitch } from "@/components/LangSwitch";
import { api, type HotelCandidate, type Lang } from "@/lib/api";
import { parseLang, t } from "@/lib/i18n";

function Home() {
  const router = useRouter();
  const params = useSearchParams();
  const lang = parseLang(params.get("lang"));
  const s = t(lang);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HotelCandidate[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setLang = (l: Lang) => router.replace(`/?lang=${l}`);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await api.search(query.trim(), lang));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
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

      {error && <p className="mt-4 text-red-700">{s.error}: {error}</p>}
      {results && results.length === 0 && <p className="mt-6 text-slate-600">{s.noResults}</p>}

      <ul className="mt-6 space-y-2">
        {results?.map((h) => (
          <li key={h.id}>
            <Link
              href={`/hotel/${encodeURIComponent(h.id)}?lang=${lang}`}
              className="block rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200 hover:ring-slate-400"
            >
              <div className="font-medium">{h.name}</div>
              <div className="text-sm text-slate-600">{h.address}</div>
              {h.rating != null && (
                <div className="mt-1 text-sm text-slate-500">
                  ★ {h.rating} · {h.review_count?.toLocaleString(lang)} {s.reviews}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
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

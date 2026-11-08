"use client";

import type { Lang } from "@/lib/api";
import { LANGS } from "@/lib/i18n";

export function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div className="flex gap-1 rounded-lg bg-white p-1 text-sm shadow-sm ring-1 ring-slate-200">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => onChange(l.code)}
          className={`rounded-md px-2.5 py-1 ${
            l.code === lang ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

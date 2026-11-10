"use client";

import { useEffect } from "react";

import type { Lang } from "@/lib/api";
import { LANGS, RTL } from "@/lib/i18n";

export function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  // Keep the page's language and text direction in step with the chosen language.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = RTL.has(lang) ? "rtl" : "ltr";
  }, [lang]);

  return (
    <select
      value={lang}
      onChange={(e) => onChange(e.target.value as Lang)}
      aria-label="Language"
      className="rounded-lg bg-white px-2.5 py-1.5 text-sm shadow-sm ring-1 ring-slate-200 outline-none hover:ring-slate-400 focus:ring-slate-900"
    >
      {LANGS.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}

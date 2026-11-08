import type { Lang } from "./api";

export const LANGS: { code: Lang; label: string }[] = [
  { code: "tr", label: "Türkçe" },
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

const strings = {
  tr: {
    title: "Otel Yorum Analizi",
    tagline: "Bir oteli arayın; farklı sitelerdeki misafir yorumlarını tek raporda görün.",
    searchPlaceholder: "Otel adı ve şehir, ör. Hilton Antalya",
    search: "Ara",
    searching: "Aranıyor…",
    noResults: "Otel bulunamadı.",
    reviews: "yorum",
    loadingReport: "Yorumlar toplanıp analiz ediliyor. Bu 20-40 saniye sürebilir…",
    overall: "Genel puan",
    overallNote: "Tüm kaynaklar 0-10'a çevrildi ve yorum sayısına göre ağırlıklandırıldı.",
    bySource: "Kaynağa göre puan",
    topics: "Konulara göre",
    pros: "Artılar",
    cons: "Eksiler",
    mentions: "yorumda geçiyor",
    summary: "Özet",
    analyzedNote: (n: number, total: number) =>
      `${total.toLocaleString("tr")} yorumdan örnek olarak ${n} tanesi analiz edildi.`,
    ask: "Yorumlara sor",
    askPlaceholder: "ör. Geceleri sessiz mi? Kahvaltı nasıl?",
    askButton: "Sor",
    asking: "Yanıtlanıyor…",
    history: "Puan geçmişi",
    historyEmpty: "Puanlar her rapor oluşturulduğunda günlük olarak kaydedilir. İkinci günden itibaren burada grafik görünür.",
    back: "← Yeni arama",
    error: "Bir hata oluştu",
    demo: "Demo veri: kurgusal otel ve yorumlar",
    topicNames: {
      cleanliness: "Temizlik", staff: "Personel", location: "Konum", room: "Oda",
      breakfast: "Kahvaltı", food: "Yemek", noise: "Gürültü", wifi: "Wi-Fi",
      value: "Fiyat/performans", facilities: "Olanaklar",
    },
  },
  en: {
    title: "Hotel Review Analyzer",
    tagline: "Search a hotel and see guest reviews from different sites in one report.",
    searchPlaceholder: "Hotel name and city, e.g. Hilton Antalya",
    search: "Search",
    searching: "Searching…",
    noResults: "No hotels found.",
    reviews: "reviews",
    loadingReport: "Collecting and analyzing reviews. This can take 20-40 seconds…",
    overall: "Overall score",
    overallNote: "Every source converted to 0-10 and weighted by number of reviews.",
    bySource: "Score by source",
    topics: "By topic",
    pros: "Pros",
    cons: "Cons",
    mentions: "reviews mention this",
    summary: "Summary",
    analyzedNote: (n: number, total: number) =>
      `${n} sample reviews analyzed out of ${total.toLocaleString("en")}.`,
    ask: "Ask the reviews",
    askPlaceholder: "e.g. Is it quiet at night? How is breakfast?",
    askButton: "Ask",
    asking: "Answering…",
    history: "Score over time",
    historyEmpty: "Scores are saved daily whenever a report is built. The chart appears from the second day on.",
    back: "← New search",
    error: "Something went wrong",
    demo: "Demo data: fictional hotel and reviews",
    topicNames: {
      cleanliness: "Cleanliness", staff: "Staff", location: "Location", room: "Room",
      breakfast: "Breakfast", food: "Food", noise: "Noise", wifi: "Wi-Fi",
      value: "Value for money", facilities: "Facilities",
    },
  },
  de: {
    title: "Hotelbewertungs-Analyse",
    tagline: "Suchen Sie ein Hotel und sehen Sie Gästebewertungen verschiedener Seiten in einem Bericht.",
    searchPlaceholder: "Hotelname und Stadt, z. B. Hilton Antalya",
    search: "Suchen",
    searching: "Suche…",
    noResults: "Keine Hotels gefunden.",
    reviews: "Bewertungen",
    loadingReport: "Bewertungen werden gesammelt und analysiert. Das kann 20-40 Sekunden dauern…",
    overall: "Gesamtnote",
    overallNote: "Alle Quellen auf 0-10 umgerechnet und nach Anzahl der Bewertungen gewichtet.",
    bySource: "Note nach Quelle",
    topics: "Nach Thema",
    pros: "Vorteile",
    cons: "Nachteile",
    mentions: "Bewertungen erwähnen das",
    summary: "Zusammenfassung",
    analyzedNote: (n: number, total: number) =>
      `${n} Beispielbewertungen von ${total.toLocaleString("de")} analysiert.`,
    ask: "Bewertungen fragen",
    askPlaceholder: "z. B. Ist es nachts ruhig? Wie ist das Frühstück?",
    askButton: "Fragen",
    asking: "Antwort wird erstellt…",
    history: "Note im Zeitverlauf",
    historyEmpty: "Die Noten werden bei jedem Bericht täglich gespeichert. Ab dem zweiten Tag erscheint hier ein Diagramm.",
    back: "← Neue Suche",
    error: "Ein Fehler ist aufgetreten",
    demo: "Demodaten: fiktives Hotel und Bewertungen",
    topicNames: {
      cleanliness: "Sauberkeit", staff: "Personal", location: "Lage", room: "Zimmer",
      breakfast: "Frühstück", food: "Essen", noise: "Lärm", wifi: "WLAN",
      value: "Preis-Leistung", facilities: "Ausstattung",
    },
  },
} as const;

export type Strings = (typeof strings)["en"];

export function t(lang: Lang): Strings {
  return strings[lang] as Strings;
}

export function parseLang(value: string | null | undefined): Lang {
  return value === "tr" || value === "de" || value === "en" ? value : "tr";
}

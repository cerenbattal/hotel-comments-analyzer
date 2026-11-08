export type Lang = "tr" | "en" | "de";

export interface HotelCandidate {
  id: string;
  name: string;
  address: string | null;
  rating: number | null;
  review_count: number | null;
}

export interface SourceScore {
  source: string;
  source_label: string;
  rating: number | null;
  scale_max: number;
  score_10: number | null;
  review_count: number;
  url: string | null;
  attribution: string | null;
}

export interface TopicScore {
  topic: string;
  score_10: number;
  positive: number;
  negative: number;
}

export interface Point {
  text: string;
  mentions: number;
  quotes: string[];
}

export interface Report {
  hotel_id: string;
  hotel_name: string;
  address: string | null;
  lang: Lang;
  overall_score_10: number | null;
  total_reviews: number;
  analyzed_reviews: number;
  sources: SourceScore[];
  topics: TopicScore[];
  pros: Point[];
  cons: Point[];
  summary: string;
}

export interface ReportJob {
  status: "running" | "done" | "failed";
  report: Report | null;
  error: string | null;
}

export interface HistoryPoint {
  source: string;
  day: string; // YYYY-MM-DD
  score_10: number | null;
  review_count: number;
}

export interface AskAnswer {
  answer: string;
  quotes: string[];
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  search: (q: string, lang: Lang) =>
    request<HotelCandidate[]>(`/api/hotels/search?q=${encodeURIComponent(q)}&lang=${lang}`),
  startReport: (id: string, lang: Lang) =>
    request<ReportJob>(`/api/hotels/${encodeURIComponent(id)}/report?lang=${lang}`, {
      method: "POST",
    }),
  reportStatus: (id: string, lang: Lang) =>
    request<ReportJob>(`/api/hotels/${encodeURIComponent(id)}/report?lang=${lang}`),
  history: (id: string) =>
    request<HistoryPoint[]>(`/api/hotels/${encodeURIComponent(id)}/history`),
  ask: (id: string, question: string, lang: Lang) =>
    request<AskAnswer>(`/api/hotels/${encodeURIComponent(id)}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, lang }),
    }),
};

"use client";

import { useEffect, useState } from "react";

import type { HotelCandidate } from "./api";

export const MAX_COMPARE = 4;
const KEY = "compare-hotels";

/** Hotels picked for comparison, remembered in this browser only. */
export function useCompareList() {
  const [items, setItems] = useState<HotelCandidate[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      // Storage unavailable (private mode etc.): start empty.
    }
  }, []);

  function save(next: HotelCandidate[]) {
    setItems(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Not persisted; the list still works for this page view.
    }
  }

  return {
    items,
    has: (id: string) => items.some((h) => h.id === id),
    toggle: (hotel: HotelCandidate) =>
      items.some((h) => h.id === hotel.id)
        ? save(items.filter((h) => h.id !== hotel.id))
        : items.length < MAX_COMPARE && save([...items, hotel]),
    clear: () => save([]),
  };
}

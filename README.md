# Hotel Comments Analyzer

Search a hotel and see its guest reviews from several sites in one report: a score per source,
a normalized overall score (0-10), the main pros and cons with real quotes, scores by topic, a
score-over-time chart, and an "ask the reviews" box. Up to 4 hotels can be compared side by side,
and any report or comparison can be saved as PDF (browser print, with a print-friendly layout). Reports are available in Turkish, English and German, and reviews in
any language are analyzed together.

MVP sources: **Google Places API** and **Tripadvisor Content API** (each returns the rating, the
review count and up to 5 reviews per hotel). Booking.com, Expedia/Hotels.com and Agoda need
partner access and are planned for later.

## Structure

```
backend/   FastAPI service: source connectors, score normalization, Claude analysis
frontend/  Next.js app: search page and hotel report page
```

### How a report is built

1. **Fetch**: Google Places details for the hotel, then the matching Tripadvisor location.
   A source that fails is skipped; the report still builds from the others.
2. **Normalize**: every rating is mapped linearly to 0-10 (1/5 → 0, 5/5 → 10). The overall score
   is a weighted average, with weights growing with log(review count).
3. **Extract** (`claude-haiku-5-5`): each review is tagged with topics (cleanliness, staff,
   location, room, breakfast, food, noise, wifi, value, facilities), sentiment, and short pro/con
   phrases. Structured output, 25 reviews per call.
4. **Aggregate** (plain code): topic scores = share of positive mentions × 10.
5. **Summarize** (`claude-sonnet-5-5`): ranked pros and cons with quotes, and a 3-4 sentence
   summary in the reader's language. Server-side refusal fallbacks are enabled.

Reports are built in a background task: `POST /report` starts a build and the page polls
`GET /report` until it is done. Finished reports are stored in the database and reused for
6 hours. Each build also saves every source's score for that day, which feeds the
"score over time" chart. Raw review text is kept only in memory (Google's terms limit storing it).

## Running locally

### With Docker (simplest)

```bash
cp backend/.env.example backend/.env   # then add your keys to backend/.env
docker compose up --build
```

App: http://localhost:3000 · API docs: http://localhost:8000/docs · Postgres runs in its own
container and keeps its data in a Docker volume.

### Without Docker

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add keys; leave the source keys empty for demo mode
uvicorn app.main:app --reload --port 8000
pytest
```

Frontend (Node 20+):

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev            # http://localhost:3000
```

**Demo mode:** with no Google or Tripadvisor key, search always returns the bundled *fictional*
hotels (`backend/app/data/demo_*.json`) so the app can be tried end to end. An Anthropic API
key is still needed for the analysis.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/health` | `{ok, demo_mode}` |
| GET | `/api/hotels/search?q=&lang=` | Hotel candidates (Google Places) |
| POST | `/api/hotels/{id}/report?lang=tr\|en\|de` | Start a build, or return a fresh report |
| GET | `/api/hotels/{id}/report?lang=` | `{status: running\|done\|failed, report, error}` |
| GET | `/api/hotels/{id}/history` | Daily score per source |
| POST | `/api/hotels/{id}/ask` | `{question, lang}` → `{answer, quotes}` |

## Terms to respect

- Show Google and Tripadvisor attribution next to their data (the report links each source).
- Google limits how long review content may be stored; reviews are only cached in memory.
- Do not scrape Booking.com, Expedia, Agoda or Airbnb; their terms forbid it.

## Next steps

- A daily job that refreshes popular hotels, so score history fills in without visits.
- Alembic migrations before the first schema change in production.
- Move builds to a job queue (Celery/Redis or similar) if one server is no longer enough.
- Sentiment by topic over time, once dated review history is available from partner or vendor data.
- Booking.com / Expedia Rapid / Agoda affiliate connectors after partner approval.

# Augur · 识机

**ML-powered football match prediction for Chinese leagues.**

🔮 **Live demo → [zooming-cat-production.up.railway.app](https://zooming-cat-production.up.railway.app)**

---

Augur combines Pi-Ratings, CatBoost, and Poisson regression to predict match outcomes and scorelines for CSL, China League One, AFC Champions League, and World Cup qualifiers. Named after the Roman augurs — priests who read patterns in nature to forecast the future.

## Features

- **Win/Draw/Loss probabilities** — CatBoost classifier trained on Pi-Ratings + form + implied odds
- **Scoreline prediction** — Poisson regression on expected goals
- **AI match analysis** — pre-match breakdowns via Claude API
- **Prediction history** — track pending, correct, and incorrect calls
- **Strength comparison** — Pi-Ratings delta between opponents
- **Auto-updates** — scheduler pulls fixtures and scores, re-runs predictions

## Stack

| Layer | Tech |
|-------|------|
| Data collection | Python scrapers (zqcf, football-data.co.uk) |
| Storage | PostgreSQL |
| Feature engineering | Pi-Ratings + recent form + odds-implied probabilities |
| Models | CatBoost (outcome) + Poisson regression (score) |
| AI analysis | Anthropic Claude API |
| Backend | FastAPI |
| Frontend | Next.js + Tailwind CSS |
| Deploy | Railway |

## Project structure

```
augur/
├── src/
│   ├── api/
│   │   ├── main.py                  # FastAPI app
│   │   └── score_predictor.py       # score prediction endpoint
│   ├── data/
│   │   ├── schema.py
│   │   ├── database.py
│   │   ├── scraper_zqcf.py          # fixture/score scraper
│   │   └── scraper_footballdata_co.py
│   ├── models/
│   │   ├── predictor.py             # CatBoost wrapper
│   │   ├── poisson_predictor.py
│   │   └── feature_engineer.py
│   ├── adapters/
│   ├── scheduler.py                 # cron jobs
│   ├── train.py
│   └── generate_ai_analysis.py
├── web/                             # Next.js frontend
│   └── app/
│       ├── page.tsx                 # today's fixtures
│       ├── match/                   # match detail
│       ├── history/                 # prediction history
│       ├── account/
│       └── pricing/
├── models/                          # serialized model files
├── Dockerfile
├── Dockerfile.scheduler
└── railway.toml
```

## Getting started

```bash
# backend
pip install -r requirements.txt
export DATABASE_URL="postgresql://localhost:5432/augur"
export ANTHROPIC_API_KEY="sk-..."
uvicorn src.api.main:app --reload

# frontend
cd web && npm install && npm run dev
```

## Status

- [x] FastAPI backend
- [x] Next.js frontend
- [x] CatBoost win/draw/loss prediction
- [x] Poisson scoreline prediction
- [x] Pi-Ratings feature engineering
- [x] Automated fixture + score ingestion
- [x] Prediction history & evaluation
- [x] AI match analysis (Claude)
- [x] User accounts & subscription
- [x] Deployed on Railway

## References

- [arXiv:2403.07669](https://arxiv.org/abs/2403.07669) — ML for Soccer Match Result Prediction (2024 survey)
- [arXiv:2309.14807](https://arxiv.org/abs/2309.14807) — CatBoost + pi-ratings benchmark
- [lucasmaystre/kickscore](https://github.com/lucasmaystre/kickscore) — Bayesian dynamic rating engine
- [soccerdata](https://github.com/probberechts/soccerdata) — football data scraping toolkit

## License

[AGPL-3.0](LICENSE)

<div align="center">

# LLM Cost Tracker

### Real-time cost monitoring and optimization platform for AI API services

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

https://llm-cost-tracker-blond.vercel.app/


</div>

---

## Quick Deploy (Free)

Click the button above to deploy instantly on **Render** (free tier). No coding needed.

### Manual Deploy

```bash
# Clone
git clone https://github.com/Mahnoor-fatima249/LLM-COST-TRACKER.git
cd LLM-COST-TRACKER

# Install
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Run
python -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000

---

## Desktop App

```bash
cd desktop
npm install
npm start        # Run desktop app
npm run build    # Build .exe installer
```

---

## Features

- **Real-time Dashboard** — WebSocket live cost tracking
- **5 AI Providers** — OpenAI, Anthropic, Google, Groq, Mistral
- **Budget Alerts** — Daily/monthly limits with Slack notifications
- **Cost Forecasting** — Monthly spend projection
- **Optimization Engine** — AI-powered cost reduction suggestions
- **Desktop App** — Electron with custom titlebar & splash screen
- **API** — RESTful API with JWT auth
- **Docker** — Ready to deploy anywhere

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + SQLAlchemy (async) |
| Database | SQLite / PostgreSQL |
| Auth | JWT + bcrypt |
| Frontend | Vanilla JS + Chart.js |
| Desktop | Electron |
| Payments | Stripe (optional) |

---

## License

MIT License

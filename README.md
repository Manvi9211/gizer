# Gizer — GitHub Developer Analytics Dashboard

> A full-stack developer analytics platform that transforms 
> raw GitHub activity into actionable insights using a 
> proprietary productivity scoring algorithm.

🔗 **Live Demo:** https://gizer.azurewebsites.net  
📁 **Tech Stack:** Python · Dash · Plotly · Pandas · SQLite · Azure App Service · GitHub REST API

---

## Screenshots

### Dashboard Overview
****<img width="1901" height="861" alt="Screenshot 2026-06-27 034527" src="https://github.com/user-attachments/assets/61c0d2d8-0e04-4734-ba80-8effd758ddd0" />


### Productivity Score
<img width="1800" height="857" alt="Screenshot 2026-06-27 034345" src="https://github.com/user-attachments/assets/2c1b6f8f-ff42-4904-a7f6-885c974d87df" />


### Language Distribution
<img width="1918" height="673" alt="Screenshot 2026-06-27 034354" src="https://github.com/user-attachments/assets/7895f7fe-1ca5-4cf2-b7df-a856bd96ef06" />


---

## Features

- **Productivity Score Algorithm** — proprietary 5-dimension 
  weighted scoring (Consistency, Volume, Collaboration, 
  Diversity, Impact)
- **Commit Quality Analysis** — NLP-based commit message scoring
- **Developer Comparison** — side-by-side radar chart comparison
- **Real-time Analytics** — commit trends, PR merge rates, 
  streak tracking
- **Auto Refresh** — APScheduler refreshes data every 6 hours

---

## Architecture
GitHub REST API

↓

Python Fetcher (fetch_github.py)

↓

SQLite Database (github_data.db)

↓

Pandas Processing (process.py)

↓

Dash Dashboard (app.py)

↓

Azure App Service (gizer.azurewebsites.net)
---

## Local Setup

```bash
git clone https://github.com/Manvi9211/gizer.git
cd gizer
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
echo "GITHUB_TOKEN=your_token" > .env
python app.py
```

Open: http://localhost:8050

---

## Tech Decisions

| Decision | Choice | Reason |
|---|---|---|
| Dashboard | Dash over Streamlit | Callback-based, 3x faster rendering |
| Storage | SQLite → PostgreSQL path | Zero setup locally, swappable for prod |
| Deployment | Azure App Service | Microsoft ecosystem alignment |
| Workers | Gunicorn single worker | SQLite doesn't support multi-writer |
| Auth | Azure App Settings | Secrets never in codebase |

---

## API Rate Limits

GitHub allows 5,000 requests/hour with token.  
Without token: 60/hour (unusable for this project).

---

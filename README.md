<div align="center">

# Gizer

**GitHub Developer Analytics Dashboard**

*Transform raw GitHub activity into actionable engineering insights.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Dash](https://img.shields.io/badge/Dash-2.x-00A9E0?style=flat-square&logo=plotly&logoColor=white)](https://dash.plotly.com)
[![Azure](https://img.shields.io/badge/Azure_App_Service-deployed-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)](https://gizer.azurewebsites.net)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/Manvi9211/gizer?style=flat-square)](https://github.com/Manvi9211/gizer/commits/main)
[![Stars](https://img.shields.io/github/stars/Manvi9211/gizer?style=flat-square&color=yellow)](https://github.com/Manvi9211/gizer/stargazers)

[**Live Demo →**](https://gizer.azurewebsites.net) · [Report Bug](https://github.com/Manvi9211/gizer/issues) · [Request Feature](https://github.com/Manvi9211/gizer/issues)

</div>

---

## Table of Contents

- [Why Gizer?](#why-gizer)
- [Key Features](#key-features)
- [Dashboard Gallery](#dashboard-gallery)
- [Architecture](#architecture)
- [Productivity Algorithm](#productivity-algorithm)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Deployment](#deployment)
- [Engineering Decisions](#engineering-decisions)
- [Performance & Scalability](#performance--scalability)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Why Gizer?

GitHub's native Insights panel shows contribution graphs and traffic. It does not answer the questions that matter when you're evaluating a developer — or evaluating yourself.

**What Gizer answers:**

- How consistent is this developer's activity across a rolling time window?
- Are their pull requests being merged, or accumulating?
- Are they working across multiple languages and repositories, or in a single context?
- What is the trend — improving, plateauing, or declining?

Gizer pulls from the GitHub REST API, persists data locally, and runs a custom five-dimension scoring model to produce a single, reproducible productivity score alongside a full suite of visualizations. Every chart is interactive. Every data point links back to a real commit, PR, or repository.

---

## Key Features

<table>
<tr>
<td width="50%">

### 📊 Productivity Score
A five-dimension composite score (0–100) built on Consistency, Volume, Collaboration, Diversity, and Impact. Each dimension is independently scored and visualized in a radar chart, so you can immediately identify which axis needs attention.

</td>
<td width="50%">

### 🔀 Pull Request Analytics
Tracks PR creation and merge timelines, computes per-month merge rates, and surfaces trends over time. Distinguishes open, merged, and closed states across the full history.

</td>
</tr>
<tr>
<td width="50%">

### 🌐 Language Distribution
Aggregates byte-level language data across all repositories, groups the long tail into "Other," and renders a ranked breakdown. Shows where the developer's technical surface area actually lives.

</td>
<td width="50%">

### 🔥 Streak Tracking
Computes longest and current active commit streaks using consecutive-day diffing on normalized UTC commit timestamps. No off-by-one errors from timezone naïvety.

</td>
</tr>
<tr>
<td width="50%">

### 📅 Activity Timeline
Monthly and weekday commit distribution charts expose working cadence — whether someone ships steadily throughout the week or in weekend bursts.

</td>
<td width="50%">

### ⚙️ Auto-Refresh Pipeline
APScheduler refreshes all GitHub data every 6 hours in the background. The dashboard reflects current state without manual intervention or full-page reloads.

</td>
</tr>
</table>

---

## Dashboard Gallery

| Dashboard Overview | Productivity Score |
|---|---|
|<img width="1901" height="861" alt="Screenshot 2026-06-27 034527" src="https://github.com/user-attachments/assets/0230eed2-1530-477b-82b0-e5ae0faf7026" />| <img width="1800" height="857" alt="Screenshot 2026-06-27 034345" src="https://github.com/user-attachments/assets/18b7a3a6-46cb-4532-902e-04a41f2b215d" />|

| Language Distribution | Activity Timeline |
|---|---|
| <img width="1918" height="673" alt="Screenshot 2026-06-27 034354" src="https://github.com/user-attachments/assets/7a1edf41-4d66-48f7-812d-505e55f0a8a1" />| <img width="1792" height="755" alt="Screenshot 2026-06-27 040742" src="https://github.com/user-attachments/assets/94373536-e88a-427d-965c-6163e461f955" />|

> **Note:** Replace placeholder paths with actual screenshots under `docs/screenshots/`.

---

## Animated Demo

> **<img width="1896" height="763" alt="gizer" src="https://github.com/user-attachments/assets/685b7107-00d1-448f-81b0-81659095608c" />**

```
[Gizer Demo]
```

---

## Architecture

```mermaid
flowchart TD
    A([GitHub REST API]) -->|PAT-authenticated requests| B[fetch_github.py\nData Fetcher]
    B -->|Repos · Commits · PRs · Languages| C[(SQLite\nLocal Store)]
    C -->|SQL reads| D[process.py\nPandas Transformer]
    D -->|analytics-ready DataFrames| E[Productivity Engine\ncalculate_productivity_score]
    D -->|time-series · distributions| F[Visualization Layer\nPlotly Figures]
    E --> G[Dash Application\napp.py]
    F --> G
    G -->|HTTP| H([Browser])
    I[scheduler.py\nAPScheduler] -->|every 6 hours| B

    style A fill:#24292e,color:#fff
    style C fill:#003B57,color:#fff
    style G fill:#00A9E0,color:#fff
    style H fill:#0078D4,color:#fff
    style I fill:#444,color:#fff
```

---

## Productivity Algorithm

The score is computed in `process.py → calculate_productivity_score()`. It produces a value from **0–100** across five independently weighted dimensions, each capped at **20 points**. A letter grade is assigned at thresholds S / A / B / C / D.

```mermaid
flowchart LR
    Input([GitHub Data\nCommits · PRs · Repos]) --> C
    Input --> V
    Input --> Col
    Input --> D
    Input --> I

    subgraph Score["Productivity Score (0–100)"]
        C["🗓 Consistency\nactive_days ÷ date_range × 20"]
        V["📦 Volume\navg commits/day × 4, cap 20"]
        Col["🤝 Collaboration\nPR merge_rate × 20"]
        D["🌐 Diversity\nlanguage_count × 3, cap 20"]
        I["⭐ Impact\n(stars × 0.5 + forks × 1.5) ÷ 10"]
    end

    C --> Total([Total Score\n+ Letter Grade])
    V --> Total
    Col --> Total
    D --> Total
    I --> Total
```

### Dimension Breakdown

| Dimension | Formula | Max | Rationale |
|---|---|---|---|
| **Consistency** | `(active_days / date_range) * 20` | 20 | Rewards regular shipping cadence over bursty activity |
| **Volume** | `min(avg_commits_per_active_day * 4, 20)` | 20 | Counts commits per active day to avoid penalizing vacations |
| **Collaboration** | `(merged_prs / total_prs) * 20` | 20 | Merge rate is a proxy for code review engagement |
| **Diversity** | `min(language_count * 3, 20)` | 20 | Breadth across languages indicates full-stack capability |
| **Impact** | `min((stars*0.5 + forks*1.5) / 10, 20)` | 20 | Forks weighted higher than stars as a signal of reuse |

**Grade thresholds:** S ≥ 85 · A ≥ 70 · B ≥ 55 · C ≥ 40 · D < 40

---

## Technology Stack

**Frontend**

![Dash](https://img.shields.io/badge/Dash-2.x-00A9E0?style=flat-square&logo=plotly)
![Plotly](https://img.shields.io/badge/Plotly-5.x-3F4F75?style=flat-square&logo=plotly)

**Backend**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.x-4B8BBE?style=flat-square)

**Analytics**

![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?style=flat-square&logo=pandas)

**Database**

![SQLite](https://img.shields.io/badge/SQLite-3.x-003B57?style=flat-square&logo=sqlite)

**Cloud**

![Azure](https://img.shields.io/badge/Azure_App_Service-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)

**APIs**

![GitHub API](https://img.shields.io/badge/GitHub_REST_API-v3-24292e?style=flat-square&logo=github)

**Developer Tools**

![Git](https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)

---

## Project Structure

```
gizer/
├── app.py                  # Dash application, layout, and callbacks
├── db.py                   # SQLite connection and schema initialization
├── fetch_github.py         # GitHub REST API client and data ingestion
├── process.py              # Pandas transformations and analytics engine
├── scheduler.py            # APScheduler background refresh job
├── startup.sh              # Azure App Service startup script
├── requirements.txt        # Python dependencies
├── .gitignore
├── .env                    # Local secrets (never committed)
├── .github/
│   └── workflows/          # CI pipeline definitions
├── zipcheck/               # Deployment artifact utilities
└── docs/
    └── screenshots/        # README images (add your own)
```

---

## Installation

### Prerequisites

- Python 3.11+
- A GitHub Personal Access Token with `repo` and `read:user` scopes

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Manvi9211/gizer.git
cd gizer

# 2. Create and activate a virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env   # or create .env manually — see Configuration
```

---

## Configuration

Create a `.env` file in the project root:

```env
# Required
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional — override the target GitHub username (defaults to token owner)
GITHUB_USERNAME=your_github_username
```

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | ✅ | GitHub Personal Access Token. Needs `repo`, `read:user` scopes. |
| `GITHUB_USERNAME` | ❌ | Target username to analyze. Defaults to the token's owner. |

> **Security:** Never commit `.env` to version control. The `.gitignore` excludes it by default. For production, use Azure App Settings (see [Deployment](#deployment)).

---

## Usage

```bash
# Run the development server
python app.py
```

The dashboard will be available at `http://localhost:8050`.

On first run, `fetch_github.py` populates the SQLite database. Subsequent runs use cached data and refresh every 6 hours via the scheduler. To force a manual refresh, restart the process or call the fetch functions directly.

---

## Deployment

Gizer is deployed to **Azure App Service** using a startup script.

### Environment Variables on Azure

Store secrets in **Azure App Service → Configuration → Application settings** rather than in any committed file:

| Setting | Value |
|---|---|
| `GITHUB_TOKEN` | Your GitHub PAT |
| `GITHUB_USERNAME` | Target username |

### Startup Script

`startup.sh` is configured as the startup command in Azure. It launches Gunicorn with the correct binding for App Service:

```bash
gunicorn --bind=0.0.0.0:8000 app:server
```

### CI/CD

The `.github/workflows/` directory contains the GitHub Actions pipeline. On push to `main`, the workflow packages the application and deploys to Azure App Service via the Azure Web Apps Deploy action.

---

## Engineering Decisions

<details>
<summary><strong>Dashboard Framework — Dash over Streamlit</strong></summary>

Streamlit re-runs the entire script on every widget interaction, which makes it unsuitable for a multi-chart dashboard with independent interactivity. Dash's callback architecture binds specific inputs to specific outputs, enabling fine-grained reactivity without full rerenders. It also exposes the underlying Flask server, which is necessary for deploying behind Gunicorn on Azure.

</details>

<details>
<summary><strong>Database — SQLite with a migration path to PostgreSQL</strong></summary>

SQLite is appropriate here because all reads and writes originate from a single process. It eliminates infrastructure overhead for a single-user analytics tool while keeping the data layer decoupled through a `get_connection()` abstraction in `db.py`. Swapping to PostgreSQL requires only changing the connection string — no query rewrites are needed since the SQL used is ANSI-compatible.

</details>

<details>
<summary><strong>Data Layer — Pandas over raw SQL aggregations</strong></summary>

Aggregations like streak computation and language grouping are more legibly expressed in Pandas than in SQL, and the dataset size (one developer's GitHub history) comfortably fits in memory. `process.py` is kept stateless — every function accepts a `dfs` dict and returns a clean DataFrame — making it straightforward to unit test without a live database.

</details>

<details>
<summary><strong>Authentication — GitHub PAT over OAuth</strong></summary>

For a single-developer analytics tool, a Personal Access Token stored in environment variables is simpler and sufficient. OAuth would add callback routing, session management, and token storage complexity. The PAT approach is production-safe when tokens are stored in Azure App Settings rather than source code.

</details>

<details>
<summary><strong>Scheduling — APScheduler over cron</strong></summary>

APScheduler runs in-process, which avoids the need for a separate cron container or Azure Function. It is sufficient for a 6-hour refresh interval. For higher-frequency polling or distributed deployments, the fetch logic can be extracted into a separate worker without changes to the analytics layer.

</details>

---

## Performance & Scalability

**Caching strategy:** Data is fetched once per 6-hour window and persisted in SQLite. The dashboard reads from the local database on every page load rather than hitting the GitHub API, eliminating latency and rate-limit exposure during user interactions.

**API rate limits:** The GitHub REST API allows 5,000 authenticated requests per hour. A single full fetch for a developer with hundreds of repositories and thousands of commits typically consumes 100–400 requests depending on pagination depth. The 6-hour refresh cadence leaves substantial headroom.

**Scalability ceiling:** The current architecture is intentionally single-tenant. Scaling to multiple users would require replacing SQLite with PostgreSQL (one database per user or a shared schema with user partitioning), moving the scheduler to a dedicated worker, and adding a caching layer (Redis) in front of the Dash callbacks.

---

## Roadmap

- [ ] Containerize with Docker for portable local development
- [ ] Migrate database to PostgreSQL for multi-user support
- [ ] Add Redis caching layer for per-callback memoization
- [ ] Team Dashboard: compare multiple developers side by side
- [ ] OAuth-based GitHub login to replace manual PAT configuration
- [ ] AI-generated insight summaries using commit and PR data
- [ ] Historical analytics with point-in-time score snapshots
- [ ] Export dashboard as PDF report
- [ ] Dark / light theme toggle

---

## Contributing

Contributions are welcome. Please follow the steps below to keep the process smooth.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes, with tests where applicable
4. Ensure `process.py` functions handle empty DataFrames (existing convention)
5. Commit using conventional commits: `git commit -m "feat: add X"`
6. Push and open a Pull Request against `main`

**Before opening a PR:**
- Confirm the dashboard runs cleanly from a fresh `python app.py`
- Do not commit `.env` or any file containing tokens
- Keep PRs focused — one logical change per PR

For significant changes, open an issue first to discuss the approach.

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## Contact

**Manvi** — [@Manvi9211](https://github.com/Manvi9211)

- GitHub: [github.com/Manvi9211](https://github.com/Manvi9211)
- LinkedIn: _[ add your LinkedIn URL ]_
- Portfolio: _[ add your portfolio URL ]_
- Email: _[ add your email ]_

Live project: [gizer.azurewebsites.net](https://gizer.azurewebsites.net)

---

<div align="center">
<sub>Built with Python · Dash · Plotly · Azure</sub>
</div>

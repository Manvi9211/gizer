import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from db import initialize_db, get_connection
from fetch_github import store_all_data
from process import (
    load_dataframes, get_kpis, commit_activity_by_month,
    commit_activity_by_weekday, language_distribution,
    pr_merge_timeline, commit_streak, top_repos_by_commits
)
import sqlite3

# --- Initialize ---
initialize_db()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],  # dark theme, looks clean
    title="GitHub Dev Insights"
)

# ─────────────────────────────────────────
# LAYOUT — what the page looks like
# ─────────────────────────────────────────
app.layout = dbc.Container([

    # --- Header ---
    dbc.Row([
        dbc.Col([
            html.H1("GitHub Developer Insights",
                    className="text-center mt-4 mb-1"),
            html.P("Analyze any public GitHub profile",
                   className="text-center text-muted mb-4")
        ])
    ]),

    # --- Search Bar ---
    dbc.Row([
        dbc.Col([
            dbc.InputGroup([
                dbc.Input(
                    id="username-input",
                    placeholder="Enter GitHub username (e.g. torvalds)",
                    type="text",
                    debounce=False
                ),
                dbc.Button(
                    "Analyze",
                    id="fetch-btn",
                    color="primary",
                    n_clicks=0
                )
            ], className="mb-2"),
            html.Div(id="fetch-status", className="text-center text-info mb-3")
        ], width=6, className="mx-auto")
    ]),

    # --- KPI Cards ---
    dbc.Row(id="kpi-row", className="mb-4 g-3"),

    # --- Row 1: Commit by Month + Weekday ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Commit Activity Over Time"),
                dbc.CardBody([dcc.Graph(id="commit-monthly-chart")])
            ])
        ], width=7),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Active Days of Week"),
                dbc.CardBody([dcc.Graph(id="commit-weekday-chart")])
            ])
        ], width=5),
    ], className="mb-4"),

    # --- Row 2: Language + PR Timeline ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Language Distribution"),
                dbc.CardBody([dcc.Graph(id="language-chart")])
            ])
        ], width=5),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("PR Activity & Merge Rate"),
                dbc.CardBody([dcc.Graph(id="pr-timeline-chart")])
            ])
        ], width=7),
    ], className="mb-4"),

    # --- Row 3: Top Repos + Streaks ---
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Most Committed Repositories"),
                dbc.CardBody([dcc.Graph(id="top-repos-chart")])
            ])
        ], width=8),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Commit Streaks"),
                dbc.CardBody([
                    html.Div(id="streak-display")
                ])
            ])
        ], width=4),
    ], className="mb-4"),

    # Hidden store — holds username across callbacks
    dcc.Store(id="username-store"),

], fluid=True)


# ─────────────────────────────────────────
# CALLBACKS — what happens on user action
# ─────────────────────────────────────────

# Callback 1: Fetch data when button clicked
@callback(
    Output("fetch-status", "children"),
    Output("username-store", "data"),
    Input("fetch-btn", "n_clicks"),
    Input("username-input", "value"),
    prevent_initial_call=True
)
def fetch_data(n_clicks, username):
    """
    Triggered when Analyze button is clicked.
    Calls GitHub API, stores in DB, returns status message.
    dcc.Store saves username so other callbacks can use it.
    """
    if not username or not username.strip():
        return "Please enter a username.", None

    username = username.strip()

    try:
        store_all_data(username)
        return f"✅ Data loaded for '{username}'", username
    except Exception as e:
        return f"❌ Error: {str(e)}", None


# Callback 2: Render KPI cards
@callback(
    Output("kpi-row", "children"),
    Input("username-store", "data")
)
def update_kpis(username):
    if not username:
        return []

    dfs = load_dataframes()
    kpis = get_kpis(dfs)
    max_streak, _ = commit_streak(dfs)

    metrics = [
        ("Repos", kpis["total_repos"], "primary"),
        ("Commits", kpis["total_commits"], "success"),
        ("Total PRs", kpis["total_prs"], "info"),
        ("PR Merge Rate", f"{kpis['pr_merge_rate']}%", "warning"),
        ("Top Language", kpis["top_language"], "danger"),
        ("Total Stars ⭐", kpis["total_stars"], "secondary"),
    ]

    cards = []
    for label, value, color in metrics:
        cards.append(
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.H4(str(value), className=f"text-{color} mb-1"),
                        html.P(label, className="text-muted mb-0 small")
                    ], className="text-center")
                ]),
                width=2
            )
        )
    return cards


# Callback 3: All charts in one callback (efficient — one DB load)
@callback(
    Output("commit-monthly-chart", "figure"),
    Output("commit-weekday-chart", "figure"),
    Output("language-chart", "figure"),
    Output("pr-timeline-chart", "figure"),
    Output("top-repos-chart", "figure"),
    Output("streak-display", "children"),
    Input("username-store", "data")
)
def update_charts(username):
    if not username:
        empty = go.Figure()
        empty.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        return empty, empty, empty, empty, empty, ""

    # Single DB load — all charts share this
    dfs = load_dataframes()
    max_streak, current_streak = commit_streak(dfs)

    # Dark theme config applied to all charts
    dark = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        margin=dict(l=20, r=20, t=20, b=20)
    )

    # Chart 1: Commits by Month
    df_monthly = commit_activity_by_month(dfs)
    fig1 = px.bar(
        df_monthly, x="month", y="commit_count",
        color="commit_count",
        color_continuous_scale="Blues",
        labels={"commit_count": "Commits", "month": ""}
    )
    fig1.update_layout(**dark, coloraxis_showscale=False)

    # Chart 2: Commits by Weekday
    df_weekday = commit_activity_by_weekday(dfs)
    fig2 = px.bar(
        df_weekday, x="weekday", y="count",
        color="count",
        color_continuous_scale="Greens",
        labels={"count": "Commits", "weekday": ""}
    )
    fig2.update_layout(**dark, coloraxis_showscale=False)

    # Chart 3: Language donut
    df_lang = language_distribution(dfs)
    fig3 = px.pie(
        df_lang, names="language", values="bytes",
        hole=0.5,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig3.update_traces(textposition="inside", textinfo="percent+label")
    fig3.update_layout(**dark, showlegend=False)

    # Chart 4: PR timeline dual axis
    df_pr = pr_merge_timeline(dfs)
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        x=df_pr["month"], y=df_pr["total_prs"],
        name="Total PRs", marker_color="#4C72B0"
    ))
    fig4.add_trace(go.Scatter(
        x=df_pr["month"], y=df_pr["merge_rate"],
        name="Merge Rate %", yaxis="y2",
        line=dict(color="#FF8C00", width=2)
    ))
    fig4.update_layout(
        **dark,
        yaxis=dict(title="PR Count", color="white"),
        yaxis2=dict(
            title="Merge Rate %", overlaying="y",
            side="right", color="white"
        ),
        legend=dict(x=0, y=1.15, orientation="h", font=dict(color="white"))
    )

    # Chart 5: Top repos
    df_top = top_repos_by_commits(dfs)
    fig5 = px.bar(
        df_top, x="commit_count", y="repo_name",
        orientation="h",
        color="commit_count",
        color_continuous_scale="Purples",
        labels={"commit_count": "Commits", "repo_name": ""}
    )
    fig5.update_layout(**dark, coloraxis_showscale=False,
                       yaxis=dict(autorange="reversed"))

    # Streak display
    streak_ui = html.Div([
        html.Div([
            html.H2(f"{max_streak}", className="text-warning mb-0"),
            html.P("Longest Streak (days)", className="text-muted small")
        ], className="text-center mb-4 mt-3"),
        html.Hr(),
        html.Div([
            html.H2(f"{current_streak}", className="text-info mb-0"),
            html.P("Current Streak (days)", className="text-muted small")
        ], className="text-center mt-3")
    ])

    return fig1, fig2, fig3, fig4, fig5, streak_ui


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)
# app.py addition — second username input
# Layout addition:
dbc.Row([
    dbc.Col([
        dbc.Input(id="username2-input",
                  placeholder="Compare with (optional)...")
    ], width=4)
])

# Callback: render radar chart comparison


@callback(
    Output("comparison-chart", "figure"),
    Input("username-store", "data"),
    Input("username2-store", "data")
)
def compare_developers(user1, user2):
    if not user1 or not user2:
        return go.Figure()

    # Load data for both — you'll need separate DB tables or filter by username
    # Add username column to your DB tables (schema update needed)

    score1 = calculate_productivity_score(load_dataframes(user1))
    score2 = calculate_productivity_score(load_dataframes(user2))

    categories = ["Consistency", "Volume",
                  "Collaboration", "Diversity", "Impact"]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=[score1["consistency"], score1["volume"], score1["collaboration"],
           score1["diversity"], score1["impact"]],
        theta=categories, fill="toself", name=user1
    ))
    fig.add_trace(go.Scatterpolar(
        r=[score2["consistency"], score2["volume"], score2["collaboration"],
           score2["diversity"], score2["impact"]],
        theta=categories, fill="toself", name=user2
    ))
    fig.update_layout(
        polar=dict(bgcolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    return fig


# Change this at the bottom of app.py
if __name__ == "__main__":
    app.run(
        debug=False,        # CRITICAL — never True in production
        host="0.0.0.0",     # CRITICAL — listens on all interfaces
        port=8050
    )

"""
app.py
Dash dashboard for GitHub Developer Insights.

Fixes applied:
- fetch_data uses State (not Input) for username — prevents
  callback firing on every keystroke
- Loading spinner wraps the fetch button area
- Productivity score section added
- All callbacks handle empty data gracefully
- debug=False, host=0.0.0.0 for Azure deployment
"""

import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

from db import initialize_db
from fetch_github import store_all_data
from process import (
    load_dataframes,
    get_kpis,
    commit_activity_by_month,
    commit_activity_by_weekday,
    language_distribution,
    pr_merge_timeline,
    commit_streak,
    top_repos_by_commits,
    calculate_productivity_score,
)

# ─────────────────────────────────────────
# INIT
# ─────────────────────────────────────────

initialize_db()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="GitHub Dev Insights",
    suppress_callback_exceptions=True
)

server = app.server  # Required for Azure / gunicorn

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────


def empty_figure():
    """Blank transparent figure for unloaded charts."""
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(
            text="No data yet — enter a username above",
            showarrow=False,
            font=dict(color="#6c757d", size=13),
            xref="paper", yref="paper", x=0.5, y=0.5
        )]
    )
    return fig


DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white"),
    margin=dict(l=20, r=20, t=20, b=20)
)

# ─────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────

app.layout = dbc.Container([

    # Header
    dbc.Row(dbc.Col([
        html.H1("GitHub Developer Insights",
                className="text-center mt-4 mb-1"),
        html.P("Analyze any public GitHub profile",
               className="text-center text-muted mb-4")
    ])),

    # Search
    dbc.Row(dbc.Col([
        dbc.InputGroup([
            dbc.Input(
                id="username-input",
                placeholder="Enter GitHub username (e.g. torvalds)",
                type="text",
                debounce=False,
                n_submit=0
            ),
            dbc.Button("Analyze", id="fetch-btn", color="primary", n_clicks=0)
        ], className="mb-2"),

        # Loading spinner shown while fetch is running
        dcc.Loading(
            id="loading-fetch",
            type="circle",
            children=html.Div(id="fetch-status",
                              className="text-center text-info mt-2 mb-3")
        )
    ], width=6, className="mx-auto")),

    # KPI Cards
    dbc.Row(id="kpi-row", className="mb-4 g-3"),

    # Productivity Score Row
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Developer Productivity Score"),
                dbc.CardBody(html.Div(id="score-display"))
            ])
        ])
    ], className="mb-4", id="score-row"),

    # Row 1: Commits over time + Weekday
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Commit Activity Over Time"),
            dbc.CardBody(dcc.Graph(id="commit-monthly-chart",
                                   figure=empty_figure()))
        ]), width=7),

        dbc.Col(dbc.Card([
            dbc.CardHeader("Active Days of Week"),
            dbc.CardBody(dcc.Graph(id="commit-weekday-chart",
                                   figure=empty_figure()))
        ]), width=5),
    ], className="mb-4"),

    # Row 2: Language + PR Timeline
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Language Distribution"),
            dbc.CardBody(dcc.Graph(id="language-chart",
                                   figure=empty_figure()))
        ]), width=5),

        dbc.Col(dbc.Card([
            dbc.CardHeader("PR Activity & Merge Rate"),
            dbc.CardBody(dcc.Graph(id="pr-timeline-chart",
                                   figure=empty_figure()))
        ]), width=7),
    ], className="mb-4"),

    # Row 3: Top Repos + Streaks
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Most Committed Repositories"),
            dbc.CardBody(dcc.Graph(id="top-repos-chart",
                                   figure=empty_figure()))
        ]), width=8),

        dbc.Col(dbc.Card([
            dbc.CardHeader("Commit Streaks"),
            dbc.CardBody(html.Div(id="streak-display"))
        ]), width=4),
    ], className="mb-4"),

    # Hidden store — passes username between callbacks
    dcc.Store(id="username-store"),

], fluid=True)


# ─────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────

@callback(
    Output("fetch-status", "children"),
    Output("username-store", "data"),
    Input("fetch-btn", "n_clicks"),
    Input("username-input", "n_submit"),  # also triggers on Enter key
    State("username-input", "value"),
    prevent_initial_call=True
)
def fetch_data(n_clicks, n_submit, username):
    """
    Triggered by button click OR pressing Enter.
    Uses State for username — does NOT refire on every keystroke.
    Calls store_all_data which opens/closes DB per repo.
    """
    if not username or not username.strip():
        return "⚠️ Please enter a username.", None

    username = username.strip()

    try:
        store_all_data(username)
        return f"✅ Data loaded for '{username}'", username
    except RuntimeError as e:
        return f"❌ {str(e)}", None
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}", None


@callback(
    Output("kpi-row", "children"),
    Input("username-store", "data")
)
def update_kpis(username):
    """Renders the 6 KPI metric cards."""
    if not username:
        return []

    dfs = load_dataframes()
    kpis = get_kpis(dfs)

    metrics = [
        ("Repos",         kpis["total_repos"],   "primary"),
        ("Commits",       kpis["total_commits"],  "success"),
        ("Total PRs",     kpis["total_prs"],      "info"),
        ("PR Merge Rate", f"{kpis['pr_merge_rate']}%", "warning"),
        ("Top Language",  kpis["top_language"],   "danger"),
        ("Total Stars ⭐", kpis["total_stars"],   "secondary"),
    ]

    return [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H4(str(val), className=f"text-{color} mb-1"),
            html.P(label, className="text-muted mb-0 small")
        ], className="text-center")), width=2)
        for label, val, color in metrics
    ]


@callback(
    Output("score-display", "children"),
    Input("username-store", "data")
)
def update_score(username):
    """Renders the productivity score with radar chart."""
    if not username:
        return html.P("Enter a username to see score.",
                      className="text-muted text-center")

    dfs = load_dataframes()
    score = calculate_productivity_score(dfs)

    # Radar chart
    categories = ["Consistency", "Volume",
                  "Collaboration", "Diversity", "Impact"]
    values = [
        score["consistency"],
        score["volume"],
        score["collaboration"],
        score["diversity"],
        score["impact"]
    ]

    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(99, 179, 237, 0.2)",
        line=dict(color="#63B3ED", width=2),
        name="Score"
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 20], color="white"),
            angularaxis=dict(color="white")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        margin=dict(l=40, r=40, t=20, b=20),
        height=300,
        showlegend=False
    )

    # Grade color
    grade_color = {
        "S": "text-warning", "A": "text-success",
        "B": "text-info",    "C": "text-secondary", "D": "text-danger"
    }.get(score["grade"], "text-muted")

    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H1(f"{score['total']}/100",
                        className="text-warning mb-0 display-4"),
                html.H2(f"Grade: {score['grade']}",
                        className=f"{grade_color} mb-3"),
                html.Hr(),
                *[
                    html.Div([
                        html.Small(dim, className="text-muted"),
                        dbc.Progress(
                            value=val * 5,  # 0-20 → 0-100%
                            color="info",
                            className="mb-2",
                            style={"height": "8px"}
                        )
                    ])
                    for dim, val in zip(categories, values)
                ]
            ], className="text-center pt-3")
        ], width=4),

        dbc.Col([
            dcc.Graph(figure=fig, config={"displayModeBar": False})
        ], width=8)
    ])


@callback(
    Output("commit-monthly-chart", "figure"),
    Output("commit-weekday-chart", "figure"),
    Output("language-chart",       "figure"),
    Output("pr-timeline-chart",    "figure"),
    Output("top-repos-chart",      "figure"),
    Output("streak-display",       "children"),
    Input("username-store", "data")
)
def update_charts(username):
    """
    Single callback for all charts.
    One DB load shared across all charts = efficient.
    """
    if not username:
        empty = empty_figure()
        return empty, empty, empty, empty, empty, ""

    dfs = load_dataframes()
    max_streak, current_streak = commit_streak(dfs)

    # Chart 1: Commits by Month
    df_monthly = commit_activity_by_month(dfs)
    if df_monthly.empty:
        fig1 = empty_figure()
    else:
        fig1 = px.bar(
            df_monthly, x="month", y="commit_count",
            color="commit_count", color_continuous_scale="Blues",
            labels={"commit_count": "Commits", "month": ""}
        )
        fig1.update_layout(**DARK, coloraxis_showscale=False)

    # Chart 2: Commits by Weekday
    df_weekday = commit_activity_by_weekday(dfs)
    if df_weekday.empty:
        fig2 = empty_figure()
    else:
        fig2 = px.bar(
            df_weekday, x="weekday", y="count",
            color="count", color_continuous_scale="Greens",
            labels={"count": "Commits", "weekday": ""}
        )
        fig2.update_layout(**DARK, coloraxis_showscale=False)

    # Chart 3: Language Donut
    df_lang = language_distribution(dfs)
    if df_lang.empty:
        fig3 = empty_figure()
    else:
        fig3 = px.pie(
            df_lang, names="language", values="bytes",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        fig3.update_layout(**DARK, showlegend=False)

    # Chart 4: PR Timeline (dual axis)
    df_pr = pr_merge_timeline(dfs)
    if df_pr.empty:
        fig4 = empty_figure()
    else:
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
            **DARK,
            yaxis=dict(title="PR Count", color="white"),
            yaxis2=dict(
                title="Merge Rate %",
                overlaying="y", side="right", color="white"
            ),
            legend=dict(x=0, y=1.15, orientation="h",
                        font=dict(color="white"))
        )

    # Chart 5: Top Repos
    df_top = top_repos_by_commits(dfs)
    if df_top.empty:
        fig5 = empty_figure()
    else:
        fig5 = px.bar(
            df_top, x="commit_count", y="repo_name",
            orientation="h",
            color="commit_count", color_continuous_scale="Purples",
            labels={"commit_count": "Commits", "repo_name": ""}
        )
        fig5.update_layout(
            **DARK,
            coloraxis_showscale=False,
            yaxis=dict(autorange="reversed")
        )

    # Streak UI
    streak_ui = html.Div([
        html.Div([
            html.H2(str(max_streak), className="text-warning mb-0"),
            html.P("Longest Streak (days)", className="text-muted small")
        ], className="text-center mb-4 mt-3"),
        html.Hr(),
        html.Div([
            html.H2(str(current_streak), className="text-info mb-0"),
            html.P("Current Streak (days)", className="text-muted small")
        ], className="text-center mt-3")
    ])

    return fig1, fig2, fig3, fig4, fig5, streak_ui


# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────

if __name__ == "__main__":
    app.run(
        debug=False,
        host="0.0.0.0",
        port=8050
    )

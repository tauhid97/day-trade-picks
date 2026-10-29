"""Builds the public track-record web page (docs/index.html)."""
import html
import os

import pandas as pd

from . import config as C
from .backtest import summarize
from .live import DISCLAIMER, load_picks


def _equity_svg(r_series):
    if len(r_series) < 2:
        return "<p class='muted'>The equity curve appears after a few graded trades.</p>"
    cum = r_series.cumsum().tolist()
    cum = [0.0] + cum
    w, h, pad = 640, 200, 10
    lo, hi = min(cum + [0]), max(cum + [0])
    span = (hi - lo) or 1
    pts = [(pad + i * (w - 2 * pad) / (len(cum) - 1), h - pad - (v - lo) / span * (h - 2 * pad))
           for i, v in enumerate(cum)]
    zero_y = h - pad - (0 - lo) / span * (h - 2 * pad)
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    color = "var(--up)" if cum[-1] >= 0 else "var(--down)"
    return (f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Cumulative R'>"
            f"<line x1='{pad}' x2='{w-pad}' y1='{zero_y:.1f}' y2='{zero_y:.1f}' class='zero'/>"
            f"<polyline points='{path}' fill='none' stroke='{color}' stroke-width='2.5'/></svg>")


def _table(df, cols, headers):
    th = "".join(f"<th>{h}</th>" for h in headers)
    rows = []
    for _, r in df.iterrows():
        tds = []
        for c in cols:
            v = r.get(c)
            cls = ""
            if c in ("r_multiple", "total_R", "avg_R") and pd.notna(v) and v != "":
                cls = " class='up'" if float(v) > 0 else " class='down'" if float(v) < 0 else ""
                v = f"{float(v):+.2f}"
            elif c in ("entry", "stop", "target") and pd.notna(v):
                v = f"{float(v):.2f}"
            tds.append(f"<td{cls}>{html.escape('' if pd.isna(v) else str(v))}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<div class='tw'><table><thead><tr>{th}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def build():
    all_picks = load_picks()
    picks = all_picks[all_picks["mode"].fillna("live") == "live"]
    practice = all_picks[all_picks["mode"] == "practice"]
    graded = picks[picks["status"].notna() & (picks["status"] != "")].copy()
    for c in ("r_multiple", "pct_return"):
        graded[c] = pd.to_numeric(graded[c], errors="coerce").fillna(0.0)
    filled = graded[graded["status"] != "no_fill"].sort_values("published_at")

    if len(graded):
        s = summarize(graded)
        overall = s.iloc[0]
        kpis = [("Graded picks", int(overall["picks"])), ("Trades triggered", int(overall["filled"])),
                ("Win rate", f"{overall['win_rate_pct']}%"), ("Total", f"{overall['total_R']:+.2f}R"),
                ("Avg per trade", f"{overall['avg_R']:+.2f}R")]
        stats_html = _table(s, ["setup", "picks", "filled", "win_rate_pct", "avg_R", "total_R", "profit_factor", "max_drawdown_R"],
                            ["Setup", "Picks", "Triggered", "Win %", "Avg R", "Total R", "Profit factor", "Max DD (R)"])
    else:
        kpis = [("Graded picks", 0)]
        stats_html = "<p class='muted'>No graded picks yet. The first results appear after the first trading day.</p>"
    kpi_html = "".join(f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{l}</div></div>" for l, v in kpis)

    recent = picks.sort_values("published_at", ascending=False).head(100)
    recent_html = _table(recent, ["date", "ticker", "setup", "entry", "stop", "target", "status", "r_multiple"],
                         ["Date", "Ticker", "Setup", "Entry", "Stop", "Target", "Result", "R"]) if len(recent) else ""

    prac_html = ""
    pg = practice[practice["status"].notna() & (practice["status"] != "")].copy()
    if len(pg):
        pg["r_multiple"] = pd.to_numeric(pg["r_multiple"], errors="coerce").fillna(0.0)
        prac_html = ("<h2>Practice skills (not counted above)</h2><p class='muted'>Skills the Guard bot has benched "
                     "or that are still proving themselves. Tracked the same way, shown for transparency.</p>" +
                     _table(summarize(pg).iloc[1:], ["setup", "filled", "win_rate_pct", "avg_R", "total_R"],
                            ["Setup", "Trades", "Win %", "Avg R", "Total R"]))
    bt_html = ""
    if os.path.exists(C.BACKTEST_SUMMARY_FILE):
        bt = pd.read_csv(C.BACKTEST_SUMMARY_FILE)
        bt_html = ("<h2>Backtest (hypothetical)</h2><p class='muted'>Simulated on ~2 months of 5-minute data with "
                   "slippage. Hypothetical results have many limitations and are not the live record.</p>" +
                   _table(bt, ["setup", "filled", "win_rate_pct", "avg_R", "total_R", "profit_factor", "max_drawdown_R"],
                          ["Setup", "Trades", "Win %", "Avg R", "Total R", "Profit factor", "Max DD (R)"]))

    updated = pd.Timestamp.now(tz="America/New_York").strftime("%b %d, %Y %I:%M %p ET")
    page = TEMPLATE.format(brand=html.escape(C.BRAND_NAME), kpis=kpi_html, equity=_equity_svg(filled["r_multiple"]),
                           stats=stats_html, recent=recent_html, backtest=prac_html + bt_html,
                           disclaimer=html.escape(DISCLAIMER), updated=updated)
    os.makedirs(os.path.dirname(C.REPORT_FILE), exist_ok=True)
    open(C.REPORT_FILE, "w").write(page)
    print(f"Wrote {C.REPORT_FILE}")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{brand} - Track Record</title>
<style>
:root{{--bg:#0f1115;--card:#171a21;--fg:#e8eaed;--muted:#9aa0a6;--line:#2a2f3a;--up:#2ecc71;--down:#ff5c5c}}
@media (prefers-color-scheme: light){{:root{{--bg:#f7f8fa;--card:#fff;--fg:#1a1d23;--muted:#5f6368;--line:#e3e5e8;--up:#12804a;--down:#c62828}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:24px 16px}}h1{{margin:0 0 4px;font-size:26px}}h2{{margin:32px 0 10px;font-size:18px}}
.muted{{color:var(--muted)}}.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:18px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}}.kpi .v{{font-size:22px;font-weight:650}}
.kpi .l{{color:var(--muted);font-size:13px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}}
svg{{width:100%;height:auto}}.zero{{stroke:var(--line);stroke-dasharray:4 4}}.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
th{{color:var(--muted);font-weight:500}}.up{{color:var(--up)}}.down{{color:var(--down)}}footer{{margin-top:36px;font-size:13px;color:var(--muted)}}
</style></head><body><main>
<h1>{brand}</h1><div class="muted">Every pick, timestamped and auto-graded - wins and losses. Updated {updated}.</div>
<div class="kpis">{kpis}</div>
<h2>Cumulative result (in R)</h2><div class="card">{equity}</div>
<p class="muted">R = profit or loss measured in units of the planned risk (entry minus stop). +2R means the trade made twice what it risked.</p>
<h2>By setup</h2>{stats}
<h2>All picks</h2>{recent}
{backtest}
<footer>{disclaimer} Graded with 0.05% slippage per side; if stop and target are hit in the same 5-minute bar, the stop is counted.</footer>
</main></body></html>"""

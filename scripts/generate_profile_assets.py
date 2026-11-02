#!/usr/bin/env python3
"""Generate self-hosted, animated profile graphics from live GitHub data.

Outputs (no third-party image services involved):
  assets/contributions.svg  - animated contribution heatmap
  assets/github-stats.svg   - totals, streaks and top languages

Run by .github/workflows/profile-stats.yml using the built-in GITHUB_TOKEN.
"""
import json, os, sys, urllib.request, datetime as dt
from html import escape

USER = os.environ.get("GH_USER", "JmineSA")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
SANS = "font-family=\"'Segoe UI',-apple-system,Helvetica,Arial,sans-serif\""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
COLORS = ["#122033", "#0e4429", "#006d32", "#26a641", "#39d353"]

QUERY = """
query($login:String!){
  user(login:$login){
    repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){
      totalCount
      nodes{ languages(first:6,orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } }
    }
    contributionsCollection{
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions totalPullRequestReviewContributions
      contributionCalendar{ totalContributions
        weeks{ contributionDays{ date contributionCount contributionLevel } } }
    }
  }
}"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-assets"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {payload}")
    return payload["data"]["user"]


def streaks(days):
    counts = [d["count"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today may not have activity yet
        i -= 1
    cur = 0
    while i >= 0 and counts[i] > 0:
        cur += 1
        i -= 1
    return cur, longest


def render_heatmap(weeks, total):
    cell, gap, left, top = 16, 4, 58, 74
    step = cell + gap
    W, H = 1200, 250
    cols, labels, prev_month = "", "", None
    for ci, wk in enumerate(weeks):
        x = left + ci * step
        cells = ""
        for di, d in enumerate(wk):
            lvl = d["level"]
            y = top + di * step
            tip = f'{d["count"]} contribution{"s" if d["count"] != 1 else ""} on {d["date"]}'
            cells += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3.5" fill="{COLORS[lvl]}"><title>{escape(tip)}</title></rect>'
        cols += f'<g class="c" style="animation-delay:{ci * 0.025:.3f}s">{cells}</g>'
        m = dt.date.fromisoformat(wk[0]["date"]).strftime("%b")
        if m != prev_month and ci < len(weeks) - 2:
            labels += f'<text x="{x}" y="{top - 12}" {SANS} font-size="12" fill="#64748b">{m}</text>'
            prev_month = m
    days = "".join(f'<text x="{left - 12}" y="{top + i * step + 12}" text-anchor="end" {SANS} font-size="11" fill="#64748b">{n}</text>'
                   for i, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    last = weeks[-1][-1] if weeks else None
    legend_x = W - 44 - 5 * step - 90
    legend = f'<text x="{legend_x}" y="{H - 22}" {SANS} font-size="12" fill="#64748b">Less</text>' + "".join(
        f'<rect x="{legend_x + 34 + i * step}" y="{H - 34}" width="{cell}" height="{cell}" rx="3.5" fill="{COLORS[i]}"/>' for i in range(5)
    ) + f'<text x="{legend_x + 34 + 5 * step + 4}" y="{H - 22}" {SANS} font-size="12" fill="#64748b">More</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub contribution graph: {total} contributions in the last year">
<style>.c{{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .6s ease-out forwards}}
@keyframes pop{{from{{opacity:0;transform:scale(.4)}}to{{opacity:1;transform:scale(1)}}}}
.t{{opacity:0;animation:fi .9s .2s ease-out forwards}}@keyframes fi{{to{{opacity:1}}}}</style>
<rect width="{W}" height="{H}" rx="16" fill="#0b1220" stroke="#1e2d45"/>
<text class="t" x="32" y="38" {SANS} font-size="13" font-weight="700" fill="#64748b" letter-spacing="1.5">CONTRIBUTION ACTIVITY</text>
<text class="t" x="{W - 32}" y="38" text-anchor="end" {SANS} font-size="15" font-weight="700" fill="#39d353">{total:,} contributions in the last year</text>
{labels}{days}{cols}{legend}
</svg>'''


def render_stats(s):
    W, H = 1200, 280
    e = s is None
    v = (lambda k: "–") if e else (lambda k: f"{s[k]:,}")
    langs = [] if e else s["langs"]
    bars = ""
    if langs:
        for i, (n, pct, col) in enumerate(langs[:5]):
            y = 78 + i * 38
            bars += f'''<text x="0" y="{y}" {SANS} font-size="14" font-weight="600" fill="#e2e8f0">{escape(n)}</text>
<text x="320" y="{y}" text-anchor="end" {SANS} font-size="13" fill="#94a3b8">{pct:.1f}%</text>
<rect x="0" y="{y + 8}" width="320" height="8" rx="4" fill="#14223a"/>
<rect class="bar" x="0" y="{y + 8}" width="{max(6, 320 * pct / 100):.0f}" height="8" rx="4" fill="{col}" style="animation-delay:{0.5 + i * 0.15:.2f}s"/>'''
    else:
        bars = f'<text x="0" y="90" {SANS} font-size="14" fill="#64748b">Waiting for first refresh</text>'

    def row(y, label, val, col):
        return f'<text x="0" y="{y}" {SANS} font-size="14" fill="#94a3b8">{label}</text><text x="300" y="{y}" text-anchor="end" {SANS} font-size="20" font-weight="700" fill="{col}">{val}</text>'
    mid = row(86, "Current streak", "–" if e else f'{s["cur"]} day{"s" if s["cur"] != 1 else ""}', "#22c55e") + \
          row(126, "Longest streak", "–" if e else f'{s["longest"]} day{"s" if s["longest"] != 1 else ""}', "#38bdf8") + \
          row(166, "Public repositories", v("repos"), "#a78bfa") + \
          row(206, "Pull requests", v("prs"), "#f59e0b")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub statistics: contributions, streaks, repositories and top languages">
<style>.a{{opacity:0;animation:fi .9s ease-out forwards}}@keyframes fi{{to{{opacity:1}}}}
.bar{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:g 1.2s cubic-bezier(.2,.7,.2,1) forwards}}@keyframes g{{to{{transform:scaleX(1)}}}}
.glow{{animation:gl 3.5s ease-in-out infinite}}@keyframes gl{{50%{{opacity:.55}}}}</style>
<defs><linearGradient id="n" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#22c55e"/></linearGradient></defs>
<rect width="{W}" height="{H}" rx="16" fill="#0b1220" stroke="#1e2d45"/>
<g class="a" transform="translate(48,0)">
<text x="0" y="46" {SANS} font-size="13" font-weight="700" fill="#64748b" letter-spacing="1.5">TOTAL CONTRIBUTIONS</text>
<text class="glow" x="0" y="130" {SANS} font-size="68" font-weight="800" fill="url(#n)">{"–" if e else f'{s["total"]:,}'}</text>
<text x="0" y="158" {SANS} font-size="14" fill="#94a3b8">in the last year</text>
<text x="0" y="214" {SANS} font-size="14" fill="#cbd5e1"><tspan font-weight="700" fill="#38bdf8">{v("commits")}</tspan> commits  ·  <tspan font-weight="700" fill="#f59e0b">{v("prs")}</tspan> PRs  ·  <tspan font-weight="700" fill="#a78bfa">{v("issues")}</tspan> issues</text>
</g>
<line x1="420" y1="40" x2="420" y2="240" stroke="#1e2d45"/>
<g class="a" transform="translate(440,0)" style="animation-delay:.3s"><text x="0" y="46" {SANS} font-size="13" font-weight="700" fill="#64748b" letter-spacing="1.5">STREAKS &amp; REPOS</text>{mid}</g>
<line x1="790" y1="40" x2="790" y2="240" stroke="#1e2d45"/>
<g class="a" transform="translate(830,0)" style="animation-delay:.6s"><text x="0" y="46" {SANS} font-size="13" font-weight="700" fill="#64748b" letter-spacing="1.5">TOP LANGUAGES</text>{bars}</g>
</svg>'''


def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks, flat = [], []
    for w in cal["weeks"]:
        wk = [{"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)} for d in w["contributionDays"]]
        weeks.append(wk)
        flat.extend(wk)
    cur, longest = streaks(flat)
    tot = {}
    cols = {}
    for r in user["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            tot[n] = tot.get(n, 0) + e["size"]
            cols[n] = e["node"]["color"] or "#64748b"
    total_bytes = sum(tot.values()) or 1
    langs = [(n, 100 * b / total_bytes, cols[n]) for n, b in sorted(tot.items(), key=lambda x: -x[1])]
    cc = user["contributionsCollection"]
    stats = dict(total=cal["totalContributions"], cur=cur, longest=longest, repos=user["repositories"]["totalCount"],
                 commits=cc["totalCommitContributions"], prs=cc["totalPullRequestContributions"],
                 issues=cc["totalIssueContributions"], langs=langs)
    return weeks, stats


def write(name, svg):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)


def empty_weeks():
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks = []
    for w in range(53):
        weeks.append([{"date": (start + dt.timedelta(days=w * 7 + d)).isoformat(), "count": 0, "level": 0} for d in range(7)])
    return weeks


if __name__ == "__main__":
    if "--empty" in sys.argv:
        write("contributions.svg", render_heatmap(empty_weeks(), 0).replace("0 contributions in the last year", "Waiting for first refresh: run the “Update profile graphics” workflow"))
        write("github-stats.svg", render_stats(None))
    else:
        weeks, stats = build(fetch())
        write("contributions.svg", render_heatmap(weeks, stats["total"]))
        write("github-stats.svg", render_stats(stats))
    print("profile assets written")

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "Cyberexpert999")
TOKEN = os.environ["GH_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/stats.svg"


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


profile = gql(
    """query($u:String!){user(login:$u){name createdAt followers{totalCount}
    repositories(ownerAffiliations:OWNER,first:100,isFork:false){nodes{stargazerCount}}
    pullRequests{totalCount} issues{totalCount}}}""",
    {"u": USER},
)["user"]

created = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
commits = private = reviews = 0
for year in range(created.year, now.year + 1):
    start = max(created, datetime(year, 1, 1, tzinfo=timezone.utc))
    end = min(now, datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    c = gql(
        """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
        contributionsCollection(from:$f,to:$t){totalCommitContributions
        restrictedContributionsCount totalPullRequestReviewContributions}}}""",
        {"u": USER, "f": start.isoformat(), "t": end.isoformat()},
    )["user"]["contributionsCollection"]
    commits += c["totalCommitContributions"]
    private += c["restrictedContributionsCount"]
    reviews += c["totalPullRequestReviewContributions"]

stars = sum(n["stargazerCount"] for n in profile["repositories"]["nodes"])
rows = [
    ("Total Commits (incl. private)", commits + private),
    ("Total Stars", stars),
    ("Total PRs", profile["pullRequests"]["totalCount"]),
    ("Total Issues", profile["issues"]["totalCount"]),
    ("Followers", profile["followers"]["totalCount"]),
]
def rank(commits, prs, issues, reviews, stars, followers):
    exp = lambda x: 1 - 2 ** -x
    logn = lambda x: x / (1 + x)
    score = (
        2 * exp(commits / 250) + 3 * exp(prs / 50) + exp(issues / 25)
        + exp(reviews / 2) + 4 * logn(stars / 50) + logn(followers / 10)
    ) / 12
    pct = (1 - score) * 100
    levels = [(1, "S"), (12.5, "A+"), (25, "A"), (37.5, "A-"), (50, "B+"),
              (62.5, "B"), (75, "B-"), (87.5, "C+"), (100, "C")]
    return next(l for t, l in levels if pct <= t)


level = rank(commits + private, profile["pullRequests"]["totalCount"],
             profile["issues"]["totalCount"], reviews, stars,
             profile["followers"]["totalCount"])
name = profile["name"] or USER
body = "".join(
    f'<text x="25" y="{70 + i * 28}" class="l">{k}</text>'
    f'<text x="400" y="{70 + i * 28}" class="v" text-anchor="end">{v}</text>'
    for i, (k, v) in enumerate(rows)
)
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="550" height="{90 + len(rows) * 28}" viewBox="0 0 550 {90 + len(rows) * 28}">
<style>.t{{font:600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#58a6ff}}.l{{font:400 14px 'Segoe UI',Ubuntu,sans-serif;fill:#c9d1d9}}.v{{font:600 14px 'Segoe UI',Ubuntu,sans-serif;fill:#c9d1d9}}</style>
<rect width="100%" height="100%" rx="8" fill="#0d1117" stroke="#30363d"/>
<text x="25" y="35" class="t">{name}'s GitHub Stats</text>
{body}
<circle cx="480" cy="{45 + len(rows) * 14 + 20}" r="40" fill="none" stroke="#30363d" stroke-width="6"/>
<circle cx="480" cy="{45 + len(rows) * 14 + 20}" r="40" fill="none" stroke="#58a6ff" stroke-width="6" stroke-dasharray="200 251" transform="rotate(-90 480 {45 + len(rows) * 14 + 20})"/>
<text x="480" y="{45 + len(rows) * 14 + 30}" text-anchor="middle" style="font:700 28px 'Segoe UI',Ubuntu,sans-serif;fill:#58a6ff">{level}</text>
</svg>"""
STYLE = (
    "<style>.t{font:600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#58a6ff}"
    ".l{font:400 13px 'Segoe UI',Ubuntu,sans-serif;fill:#c9d1d9}"
    ".b{font:700 30px 'Segoe UI',Ubuntu,sans-serif;fill:#c9d1d9}"
    ".s{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:#8b949e}</style>"
)
FRAME = '<rect width="100%" height="100%" rx="8" fill="#0d1117" stroke="#30363d"/>'

cal = gql(
    """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
    totalContributions weeks{contributionDays{date contributionCount}}}}}}""",
    {"u": USER},
)["user"]["contributionsCollection"]["contributionCalendar"]
days = [d for w in cal["weeks"] for d in w["contributionDays"]]
today = now.date().isoformat()
days = [d for d in days if d["date"] <= today]
longest = run = 0
for d in days:
    run = run + 1 if d["contributionCount"] else 0
    longest = max(longest, run)
current = 0
for d in reversed(days):
    if d["contributionCount"]:
        current += 1
    elif d["date"] != today:
        break
streak_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="450" height="190" viewBox="0 0 450 190">
{STYLE}{FRAME}
<text x="25" y="35" class="t">Contribution Streak</text>
<text x="75" y="100" text-anchor="middle" class="b">{cal['totalContributions']}</text>
<text x="75" y="125" text-anchor="middle" class="s">Last 12 months</text>
<text x="225" y="100" text-anchor="middle" class="b" style="fill:#58a6ff">{current}</text>
<text x="225" y="125" text-anchor="middle" class="s">Current streak (days)</text>
<text x="375" y="100" text-anchor="middle" class="b">{longest}</text>
<text x="375" y="125" text-anchor="middle" class="s">Longest streak (days)</text>
</svg>"""

repos = gql(
    """query($u:String!){user(login:$u){repositories(ownerAffiliations:OWNER,first:100,isFork:false){
    nodes{languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}""",
    {"u": USER},
)["user"]["repositories"]["nodes"]
totals = {}
for r in repos:
    for e in r["languages"]["edges"]:
        n = e["node"]
        t = totals.setdefault(n["name"], [0, n["color"] or "#8b949e"])
        t[0] += e["size"]
top = sorted(totals.items(), key=lambda kv: -kv[1][0])[:5]
total = sum(v[0] for _, v in top) or 1
bars, labels, x = "", "", 25
for i, (lname, (size, color)) in enumerate(top):
    w = 400 * size / total
    bars += f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="10" fill="{color}"/>'
    x += w
    col, row = i % 2, i // 2
    labels += (
        f'<circle cx="{32 + col * 200}" cy="{92 + row * 24}" r="5" fill="{color}"/>'
        f'<text x="{44 + col * 200}" y="{96 + row * 24}" class="l">{lname} {100 * size / total:.1f}%</text>'
    )
langs_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="450" height="190" viewBox="0 0 450 190">
{STYLE}{FRAME}
<text x="25" y="35" class="t">Top Languages</text>
<clipPath id="c"><rect x="25" y="55" width="400" height="10" rx="5"/></clipPath>
<g clip-path="url(#c)">{bars}</g>
{labels}
</svg>"""

out_dir = os.path.dirname(OUT) or "."
os.makedirs(out_dir, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
with open(os.path.join(out_dir, "streak.svg"), "w", encoding="utf-8") as f:
    f.write(streak_svg)
with open(os.path.join(out_dir, "langs.svg"), "w", encoding="utf-8") as f:
    f.write(langs_svg)
print(f"commits={commits} private={private}")

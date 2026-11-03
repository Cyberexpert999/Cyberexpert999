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
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"commits={commits} private={private}")

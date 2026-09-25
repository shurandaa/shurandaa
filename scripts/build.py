#!/usr/bin/env python3
"""Render every SVG under assets/ and README.md from the CONFIG below.

Usage:
    python3 scripts/build.py            # render everything (fetches live GitHub stats)
    python3 scripts/build.py --offline  # skip the network; keep the existing stats card

Only the standard library is used, so this runs anywhere (incl. GitHub Actions).
"""

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ─────────────────────────────── CONFIG ────────────────────────────────
# Edit content here, then re-run the script.

USERNAME = "shurandaa"
# Card beside Tech Stack: False → Contact card, True → GitHub Stats card (refreshed daily by Actions).
SHOW_STATS = False
NAME = "Shuran Zhao"

HERO = {
    "headline": "Hi, I'm Shuran Zhao.",
    "role": "An AI-Native Software Engineer",
    "subtitle": "Building AI infrastructure, distributed systems, and intelligent developer tools.",
    "value": "// turning LLMs into reliable, observable, production-grade systems",
    "meta": ["MSCS @ Northeastern University", "Seattle", "New Grad 2027",
             "AI Infra", "Distributed Systems", "LLM / Agent Systems"],
}

# Empty URL → that button is left out of the README.
LINKS = [
    ("Blog", "blog", ""),
    ("LinkedIn", "linkedin", ""),
    ("Email", "email", "mailto:shuranz330@gmail.com"),
    ("Resume", "resume", ""),
    ("Portfolio", "portfolio", ""),
]

WHOAMI = "MSCS @ Northeastern University, Seattle · Amazon SDE Intern"
STACK = "Java / Python / Rust / Go / TypeScript / AWS"

# (icon, label, value) rows of the Contact card; the whole card links to CONTACT_URL.
CONTACT = [
    ("email", "Email", "shuranz330@gmail.com"),
    ("phone", "Phone", "+1 (206) 843-0550"),
    ("location", "Location", "Seattle, WA"),
    ("status", "Status", "Open to 2027 New Grad SWE / MLE roles"),
]
CONTACT_URL = "mailto:shuranz330@gmail.com"

FOCUS = [
    "Building AI-native developer infrastructure",
    "Working on LLM agents and distributed systems",
    "Researching applied AI / multimodal systems",
    "Learning Rust, systems design, and high-performance inference",
    "Preparing for 2027 New Grad SWE / MLE roles",
]

SKILLS = [
    ("Languages", "#58a6ff", ["Java", "Python", "Kotlin", "C++", "Go", "Rust", "TypeScript", "SQL"]),
    ("Backend / Systems", "#39c5cf", ["Spring Boot", "Node.js", "Redis", "PostgreSQL", "Docker", "REST"]),
    ("AI", "#a371f7", ["LLM", "RAG", "LangChain", "AWS Bedrock", "MCP", "Agent Systems"]),
    ("Cloud", "#56d4bc", ["AWS", "SageMaker", "EMR"]),
]

# Skills with a logo on skillicons.dev render as icons; the rest render as text chips.
SKILL_ICONS = {"Java": "java", "Python": "py", "Kotlin": "kotlin", "C++": "cpp", "Go": "go", "Rust": "rust",
               "TypeScript": "ts", "Spring Boot": "spring", "Node.js": "nodejs", "Redis": "redis",
               "PostgreSQL": "postgres", "Docker": "docker", "AWS": "aws"}

METRICS = [
    ("500+", "DSA problems solved", "#58a6ff"),
    ("2+ yrs", "engineering experience", "#39c5cf"),
    ("AI Infra", "& distributed systems", "#a371f7"),
    ("2027", "new grad · SWE / MLE", "#56d4bc"),
]

# impact: a measurable result, e.g. "p99 latency ↓ 38%"; if empty the card shows status instead.
# status defaults to "In active development"; url empty → card is not linked (e.g. internal work).
# link_label defaults to "view on GitHub  ↗" (e.g. use "read the case study  ↗" for a write-up).
PROJECTS = [
    {
        "slug": "ai-oncall",
        "name": "AI On-Call · Incident Investigation Platform",
        "desc": "Multi-agent system that auto-investigates CI/CD failures, from alarm to one-click fix.",
        "tags": ["AWS Bedrock", "MCP", "AWS CDK", "Slack", "Multi-Agent"],
        "impact": "",
        "status": "Intern Project · Finished",
        "url": f"https://github.com/{USERNAME}/{USERNAME}/blob/main/projects/ai-oncall.md",
        "link_label": "read the case study  ↗",
    },
    {
        "slug": "facial-dynamics",
        "name": "facial-dynamics · Semantic Tokens for Facial Expressions",
        "desc": "Readable, editable text tokens for facial expressions: encode, edit meaning, decode.",
        "tags": ["Python", "MediaPipe", "ARKit Blendshapes", "Multimodal", "Semantic Codec"],
        "impact": "",
        "status": "Currently working on",
        "url": "https://github.com/TianWang0810/facial-dynamics/blob/main/README.md",
    },
    {
        "slug": "echomind",
        "name": "EchoMind · Multi-Agent Runtime",
        "desc": "A runtime for orchestrating tool-using agents with shared memory, planning, and tracing.",
        "tags": ["Python", "Multi-Agent", "MCP", "Redis", "Docker"],
        "impact": "",
        "url": f"https://github.com/{USERNAME}?tab=repositories",
    },
    {
        "slug": "inference-gateway",
        "name": "High-Performance AI Inference Gateway",
        "desc": "An OpenAI-compatible gateway with request batching, caching, routing, and rate limiting.",
        "tags": ["Rust", "Go", "Redis", "Docker", "gRPC"],
        "impact": "",
        "url": f"https://github.com/{USERNAME}?tab=repositories",
    },
]

EXPERIENCE = [
    ("Amazon", "SDE Intern",
     "AI infrastructure & distributed systems · automated incident investigation · significantly reduced triage effort"),
    ("Northeastern University", "Research",
     "Applied AI & multimodal systems"),
]

# ─────────────────────────────── THEME ─────────────────────────────────

CARD_BG = "#0a1424"
TILE_BG = "#0d1b30"
BORDER = "#1f6feb"
GLOW = "#00b7ff"
TEXT = "#e6edf3"
MUTED = "#8b949e"
CYAN = "#00b7ff"
VIOLET = "#a371f7"
GREEN = "#3fb950"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
M = 6  # outer margin so the glow isn't clipped and side-by-side cards get a gap


def esc(s):
    return html.escape(str(s), quote=True)


def mono_w(text, size):
    """Approximate rendered width of monospace text."""
    return len(text) * size * 0.6


def svg(w, h, body, defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'fill="none">\n<defs>\n'
        f'<filter id="glow" x="-10%" y="-10%" width="120%" height="120%">'
        f'<feGaussianBlur stdDeviation="3"/></filter>\n'
        f'<style>.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}</style>\n{defs}</defs>\n{body}\n</svg>\n'
    )


def card(x, y, w, h, r=10):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" stroke="{GLOW}" stroke-opacity=".35" '
        f'stroke-width="2" filter="url(#glow)"/>\n'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{CARD_BG}" stroke="{BORDER}" '
        f'stroke-opacity=".75"/>\n'
    )


def text(x, y, s, size, fill=TEXT, cls="s", weight=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{esc(s)}</text>\n')


def pill(x, y, label, size=12, color=BORDER, fill=TILE_BG, h=26, fg="#c9d1d9", fill_op=1, pad=22):
    w = mono_w(label, size) + pad
    out = (f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2 - 5:.0f}" fill="{fill}" '
           f'fill-opacity="{fill_op}" stroke="{color}" stroke-opacity=".6"/>\n')
    out += text(x + w / 2, y + h / 2 + size * 0.36, label, size, fg, "m", 500, "middle")
    return out, w


def pill_row(x, y, labels, gap=8, **kw):
    out = ""
    for label in labels:
        s, w = pill(x, y, label, **kw)
        out += s
        x += w + gap
    return out


def terminal_bar(w, title):
    out = f'<path d="M{M} {M + 36}h{w - 2 * M}" stroke="{BORDER}" stroke-opacity=".35"/>\n'
    for i, c in enumerate(["#f85149", "#d29922", "#3fb950"]):
        out += f'<circle cx="{M + 20 + i * 16}" cy="{M + 18}" r="5" fill="{c}" fill-opacity=".8"/>\n'
    out += text(w / 2, M + 22, title, 12, MUTED, "m", 400, "middle")
    return out


# ─────────────────────────────── ASSETS ────────────────────────────────

def header():
    W, H = 1000, 330
    defs = (
        f'<linearGradient id="role" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/>'
        f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient>\n'
        f'<radialGradient id="halo" cx="85%" cy="15%" r="60%"><stop offset="0" stop-color="{BORDER}" '
        f'stop-opacity=".28"/><stop offset="1" stop-color="{BORDER}" stop-opacity="0"/></radialGradient>\n'
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<circle cx="2" cy="2" r="1" fill="{MUTED}" fill-opacity=".18"/></pattern>\n'
        f'<clipPath id="c"><rect x="{M}" y="{M}" width="{W - 2 * M}" height="{H - 2 * M}" rx="10"/></clipPath>\n'
    )
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += f'<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="url(#dots)"/>'
    b += f'<rect width="{W}" height="{H}" fill="url(#halo)"/>\n'
    # faint circuit traces on the right
    b += f'<g stroke="{CYAN}" stroke-opacity=".16" stroke-width="1.5">'
    for i, (y, x2) in enumerate([(70, 830), (110, 880), (150, 800), (190, 860)]):
        b += f'<path d="M{W} {y}H{x2 + 40}l-20 20H{x2}"/><circle cx="{x2}" cy="{y + 20}" r="3" fill="{CYAN}" fill-opacity=".3"/>'
    b += "</g></g>\n"

    x = 48
    b += text(x, 50, f"~/{USERNAME}", 13, MUTED, "m")
    status = "open to 2027 SWE / MLE roles"
    b += f'<circle cx="{W - 48 - mono_w(status, 13) - 12:.0f}" cy="46" r="4" fill="{GREEN}"/>'
    b += text(W - 48, 50, status, 13, MUTED, "m", 400, "end")
    b += text(x, 112, HERO["headline"], 42, TEXT, "s", 700)
    b += text(x, 164, HERO["role"], 42, "url(#role)", "s", 700)
    b += text(x, 206, HERO["subtitle"], 18, MUTED)
    b += text(x, 238, HERO["value"], 14, CYAN, "m")
    b += pill_row(x, 268, HERO["meta"], gap=8, size=12)
    return svg(W, H, b, defs)


ICONS = {
    "blog": '<path d="M3 13l1-3.5 7-7 2.5 2.5-7 7L3 13z" stroke-linejoin="round"/>',
    "linkedin": '<rect x="2" y="2" width="12" height="12" rx="2"/><path d="M5 7v4M5 5v.01M8 11V7m0 1.8C8 7.6 9 7 10 7s1.5.7 1.5 1.8V11"/>',
    "email": '<rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5L8 9l5.5-4.5"/>',
    "resume": '<path d="M4 2h5.5L12.5 5v9H4z M9.5 2v3h3 M6 8.5h4.5 M6 11h4.5" stroke-linejoin="round"/>',
    "portfolio": '<circle cx="8" cy="8" r="6"/><ellipse cx="8" cy="8" rx="2.6" ry="6"/><path d="M2 8h12"/>',
    "phone": '<rect x="4.5" y="1.5" width="7" height="13" rx="1.5"/><path d="M7 12.5h2"/>',
    "location": '<path d="M8 14.5s4.5-4.2 4.5-8a4.5 4.5 0 00-9 0c0 3.8 4.5 8 4.5 8z" stroke-linejoin="round"/><circle cx="8" cy="6.5" r="1.6"/>',
    "status": '<circle cx="8" cy="8" r="6"/><path d="M5.5 8.2l1.8 1.8 3.3-3.6" stroke-linejoin="round"/>',
}


def cta(label, icon):
    size = 13
    w = round(16 + 16 + 9 + mono_w(label, size) + 16)
    H = 38
    b = (f'<rect x="1" y="1" width="{w - 2}" height="{H - 2}" rx="8" fill="{CARD_BG}" stroke="{BORDER}" '
         f'stroke-opacity=".8"/>\n'
         f'<g transform="translate(16 11)" stroke="{CYAN}" stroke-width="1.4" stroke-linecap="round">'
         f'{ICONS[icon]}</g>\n')
    b += text(41, H / 2 + size * 0.36, label, size, TEXT, "m", 500)
    return svg(w, H, b)


def current_focus():
    W, H = 680, 380
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += terminal_bar(W, f"{USERNAME}@seattle: ~ — zsh")
    x, lh, fs = 30, 25, 13.5

    def cmd(y, name):
        return (f'<text x="{x}" y="{y}" class="m" font-size="{fs}"><tspan fill="{GREEN}">$</tspan>'
                f'<tspan fill="{TEXT}" font-weight="600"> {name}</tspan></text>\n')

    y = 78
    b += cmd(y, "whoami")
    b += text(x, y + lh, WHOAMI, fs, "#c9d1d9", "m")
    y += 2 * lh + 10
    b += cmd(y, "current_focus")
    for line in FOCUS:
        y += lh
        b += (f'<text x="{x}" y="{y}" class="m" font-size="{fs}"><tspan fill="{CYAN}">&gt;</tspan>'
              f'<tspan fill="#c9d1d9"> {esc(line)}</tspan></text>\n')
    y += lh + 10
    b += cmd(y, "stack")
    b += text(x, y + lh, STACK, fs, "#c9d1d9", "m")
    y += 2 * lh + 5
    b += text(x, y, "$", fs, GREEN, "m")
    b += (f'<rect x="{x + 16}" y="{y - 12}" width="8.5" height="16" fill="{TEXT}">'
          f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.2s" '
          f'repeatCount="indefinite"/></rect>\n')
    return svg(W, H, b)


# Pixel-art cat coding behind a laptop. One character = one pixel.
CAT = [
    "....OO............OO....",
    "....OWO..........OWO....",
    "....OWPO........OPWO....",
    "....OWWWOOOOOOOOWWWO....",
    "...OWWWWWWWWWWWWWWWWO...",
    "...OWWWWWWWWWWWWWWWWO...",
    "...OWWEEWWWWWWWWEEWWO...",
    "...OWWEEWWWWWWWWEEWWO...",
    "...OWWWWWWWPPWWWWWWWO...",
    "...OWSWWWWSWWSWWWWSWO...",
    "....OWWWWWWWWWWWWWWO....",
    "..GGWWGGGGGGGGGGGGWWGG..",
    "..GLLLLLLLLLLLLLLLLLLG..",
    "..GLLLLLLLLCCLLLLLLLLG..",
    "..GLLLLLLLCCCCLLLLLLLG..",
    "..GLLLLLLLCCCCLLLLLLLG..",
    "..GLLLLLLLLCCLLLLLLLLG..",
    "..GLLLLLLLLLLLLLLLLLLG..",
    ".GGGGGGGGGGGGGGGGGGGGGG.",
]
CAT_COLORS = {"O": "#3b4a66", "W": "#e6edf3", "S": "#f2a7c3", "P": "#f778ba", "E": CYAN,
              "G": "#484f58", "L": "#21262d", "C": CYAN}


def mascot():
    W, H = 340, 380
    u = 7
    aw, ah = len(CAT[0]) * u, len(CAT) * u
    ax, ay = (W - aw) / 2, 92
    defs = (f'<radialGradient id="screen" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{CYAN}" '
            f'stop-opacity=".22"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>')
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += text(26, 38, "PAIR PROGRAMMER", 11, MUTED, "m", 600, extra='letter-spacing="1.5"')
    b += (f'<circle cx="{W - 90}" cy="34" r="3.5" fill="{GREEN}"><animate attributeName="opacity" '
          f'values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    b += text(W - 26, 38, "ONLINE", 11, GREEN, "m", 600, "end", 'letter-spacing="1.5"')
    b += f'<ellipse cx="{W / 2}" cy="{ay + ah * .55}" rx="{aw * .75}" ry="{ah * .6}" fill="url(#screen)"/>\n'

    # floating code glyphs
    for gx, gy, glyph, color, dur in [(58, 104, "</>", CYAN, 4), (W - 62, 128, "{ }", VIOLET, 5),
                                      (70, 196, "λ", VIOLET, 4.5), (W - 70, 206, "0x1", CYAN, 5.5)]:
        b += (f'<g opacity=".7">{text(gx, gy, glyph, 14, color, "m", 700, "middle").strip()}'
              f'<animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" '
              f'dur="{dur}s" repeatCount="indefinite"/></g>\n')

    b += f'<g shape-rendering="crispEdges">'
    for r, row in enumerate(CAT):
        for c, ch in enumerate(row):
            if ch in CAT_COLORS:
                b += (f'<rect x="{ax + c * u:.0f}" y="{ay + r * u:.0f}" width="{u}" height="{u}" '
                      f'fill="{CAT_COLORS[ch]}"/>')
    # blink: briefly paint fur over the top half of each eye
    b += '<g opacity="0">'
    for c in (6, 16):
        b += f'<rect x="{ax + c * u:.0f}" y="{ay + 6 * u:.0f}" width="{2 * u}" height="{u}" fill="#e6edf3"/>'
    b += ('<animate attributeName="opacity" values="0;0;1;0" keyTimes="0;.94;.97;1" dur="4s" '
          'repeatCount="indefinite"/></g></g>\n')

    b += text(W / 2, 318, NAME, 16, TEXT, "s", 700, "middle")
    b += text(W / 2, 342, "agents · infra · inference", 12, MUTED, "m", 400, "middle")
    return svg(W, H, b, defs)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"{USERNAME}-profile"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats():
    api = "https://api.github.com"
    repos = fetch_json(f"{api}/users/{USERNAME}/repos?per_page=100&type=owner")
    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    commits = fetch_json(f"{api}/search/commits?q=author:{USERNAME}&per_page=1")["total_count"]
    prs = fetch_json(f"{api}/search/issues?q=author:{USERNAME}+type:pr&per_page=1")["total_count"]
    issues = fetch_json(f"{api}/search/issues?q=author:{USERNAME}+type:issue&per_page=1")["total_count"]

    # The public contribution calendar: each day cell has an id, and a tooltip "N contributions on …".
    req = urllib.request.Request(f"https://github.com/users/{USERNAME}/contributions",
                                 headers={"User-Agent": f"{USERNAME}-profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode()
    dates = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', page))
    dates = {cell: day for day, cell in dates.items()}
    counts = {}
    for cell, tip in re.findall(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if cell in dates:
            m = re.match(r"(\d+) contribution", tip.strip())
            counts[dates[cell]] = int(m.group(1)) if m else 0
    if not counts:
        raise RuntimeError("could not parse contribution calendar")
    days = sorted(counts)
    year = str(dt.date.today().year)
    this_year = sum(c for d, c in counts.items() if d.startswith(year))
    streak, i = 0, len(days) - 1
    if counts[days[i]] == 0:  # today not yet contributed doesn't break the streak
        i -= 1
    while i >= 0 and counts[days[i]] > 0:
        streak, i = streak + 1, i - 1
    return [
        ("Total Stars", stars, "#d29922"),
        ("Total Commits", commits, CYAN),
        ("Total PRs", prs, VIOLET),
        ("Total Issues", issues, "#58a6ff"),
        (f"Contributions {year}", this_year, GREEN),
        ("Current Streak", f"{streak} day{'s' if streak != 1 else ''}", "#f0883e"),
    ]


def contact():
    W, H = 500, 330
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += text(28, 44, "Contact", 17, TEXT, "s", 700)
    b += text(W - 28, 44, "let's talk ↗", 12, CYAN, "m", 500, "end")
    th, gap = 54, 9
    for i, (icon, label, value) in enumerate(CONTACT):
        y = 62 + i * (th + gap)
        b += (f'<rect x="28" y="{y}" width="{W - 56}" height="{th}" rx="8" fill="{TILE_BG}" stroke="{BORDER}" '
              f'stroke-opacity=".35"/>\n'
              f'<rect x="42" y="{y + 11}" width="32" height="32" rx="8" fill="{CYAN}" fill-opacity=".1" '
              f'stroke="{CYAN}" stroke-opacity=".35"/>\n'
              f'<g transform="translate(50 {y + 19})" stroke="{CYAN}" stroke-width="1.4" '
              f'stroke-linecap="round">{ICONS[icon]}</g>\n')
        b += text(90, y + 22, label.upper(), 10.5, MUTED, "m", 500, extra='letter-spacing=".6"')
        b += text(90, y + 42, value, 15, TEXT, "s", 600)
    return svg(W, H, b)


def github_stats(stats):
    W, H = 500, 330
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += text(28, 44, "GitHub Stats", 17, TEXT, "s", 700)
    b += text(W - 28, 44, f"@{USERNAME}", 12, MUTED, "m", 400, "end")
    tw, th, gx, gy = 212, 74, 20, 12
    for i, (label, value, color) in enumerate(stats):
        x = 28 + (i % 2) * (tw + gx)
        y = 64 + (i // 2) * (th + gy)
        b += (f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="8" fill="{TILE_BG}" stroke="{BORDER}" '
              f'stroke-opacity=".35"/>\n'
              f'<rect x="{x}" y="{y + 16}" width="3" height="{th - 32}" rx="1.5" fill="{color}"/>\n')
        b += text(x + 18, y + 27, label.upper(), 10.5, MUTED, "m", 500, extra='letter-spacing=".6"')
        b += text(x + 18, y + 58, f"{value:,}" if isinstance(value, int) else value, 25, TEXT, "s", 700)
    return svg(W, H, b)


ICON_CACHE = ASSETS / "icons"


def skill_icon(slug, x, y, size, n):
    """Inline a skillicons.dev logo (cached locally), with its ids namespaced to avoid clashes."""
    path = ICON_CACHE / f"{slug}.svg"
    if not path.exists():
        ICON_CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(f"https://skillicons.dev/icons?i={slug}",
                                     headers={"User-Agent": f"{USERNAME}-profile"})
        with urllib.request.urlopen(req, timeout=30) as r:
            path.write_text(r.read().decode())
    src = path.read_text().strip()
    src = re.sub(r'id="([^"]+)"', rf'id="i{n}-\1"', src)
    src = re.sub(r'(url\(#|href="#)([^")]+)', rf'\1i{n}-\2', src)
    return re.sub(r'<svg width="\d+" height="\d+"', f'<svg x="{x}" y="{y}" width="{size}" height="{size}"',
                  src, count=1) + "\n"


def skills(wide):
    """Half-width card (4 stacked groups) beside the stats card, or full-width with groups in 2 columns."""
    W, H = (1000, 210) if wide else (500, 330)
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += text(28, 44, "Tech Stack & Skills", 17, TEXT, "s", 700)
    size, n = 32, 0
    for i, (group, color, items) in enumerate(SKILLS):
        x0 = 28 + (i % 2) * 486 if wide else 28
        y = 76 + (i // 2 if wide else i) * 62
        b += f'<circle cx="{x0 + 4}" cy="{y - 4}" r="3" fill="{color}"/>'
        b += text(x0 + 14, y, group.upper(), 10.5, color, "m", 600, extra='letter-spacing=".8"')
        x = x0
        for item in items:
            if item in SKILL_ICONS:
                b += skill_icon(SKILL_ICONS[item], x, y + 10, size, n)
                x, n = x + size + 7, n + 1
            else:
                s_, w = pill(x, y + 10 + (size - 25) / 2, item, size=11.5, color=color, fill=color,
                             fill_op=.08, h=25, fg=TEXT, pad=14)
                b += s_
                x += w + 6
    return svg(W, H, b)


def metrics():
    W, H = 1000, 118
    n, gap = len(METRICS), 14
    tw = (W - 2 * M - gap * (n - 1)) / n
    b = ""
    for i, (value, label, color) in enumerate(METRICS):
        x = M + i * (tw + gap)
        b += card(x, M, tw, H - 2 * M)
        b += f'<path d="M{x + 22} {M + 18}h32" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        b += text(x + 22, 66, value, 30, TEXT, "s", 700)
        b += text(x + 22, 92, label, 13, MUTED, "m")
    return svg(W, H, b)


def section(title):
    W, H = 1000, 44
    b = text(M + 2, 28, f"// {title}", 15, CYAN, "m", 600, extra='letter-spacing="1"')
    x = M + 2 + mono_w(f"// {title}", 15) + 16
    b += f'<path d="M{x:.0f} 23H{W - M}" stroke="{BORDER}" stroke-opacity=".45"/>'
    return svg(W, H, b)


def project(i, p):
    W, H = 1000, 196
    defs = (f'<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}"/>'
            f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient>')
    b = card(M, M, W - 2 * M, H - 2 * M)
    b += f'<rect x="{M}" y="{M + 22}" width="3" height="{H - 2 * M - 44}" rx="1.5" fill="url(#bar)"/>'
    x = 36
    b += text(x, 44, f"{i:02d} / FEATURED PROJECT", 11, MUTED, "m", 500, extra='letter-spacing="1.2"')
    b += text(x, 80, p["name"], 23, TEXT, "s", 700)
    b += text(x, 110, p["desc"], 15, MUTED)
    b += pill_row(x, 134, p["tags"], gap=7, size=12, h=26)

    bx, bw = 716, 250
    b += (f'<rect x="{bx}" y="30" width="{bw}" height="{H - 60}" rx="8" fill="{TILE_BG}" stroke="{BORDER}" '
          f'stroke-opacity=".35"/>\n')
    if p["impact"]:
        b += text(bx + 18, 60, "IMPACT", 10.5, MUTED, "m", 600, extra='letter-spacing="1"')
        b += text(bx + 18, 92, p["impact"], 17, GREEN, "s", 700)
    else:
        b += text(bx + 18, 60, "STATUS", 10.5, MUTED, "m", 600, extra='letter-spacing="1"')
        status = p.get("status", "In active development")
        dot = CYAN if "Finished" in status else GREEN
        b += f'<circle cx="{bx + 23}" cy="86" r="4" fill="{dot}"/>'
        b += text(bx + 34, 91, status, 15, TEXT, "s", 600)
    b += f'<path d="M{bx + 18} 118h{bw - 36}" stroke="{BORDER}" stroke-opacity=".3"/>'
    if p["url"]:
        b += text(bx + 18, 146, p.get("link_label", "view on GitHub  ↗"), 13, CYAN, "m", 500)
    else:
        b += text(bx + 18, 146, "internal · code not public", 13, MUTED, "m", 500)
    return svg(W, H, b, defs)


def experience():
    W = 1000
    H = 60 + 74 * len(EXPERIENCE)
    b = card(M, M, W - 2 * M, H - 2 * M)
    x = 36
    top, bottom = 58, 58 + 74 * (len(EXPERIENCE) - 1)
    b += f'<path d="M{x} {top}V{bottom}" stroke="{BORDER}" stroke-opacity=".5" stroke-width="1.5"/>'
    for i, (org, role, detail) in enumerate(EXPERIENCE):
        y = top + i * 74
        color = CYAN if i == 0 else VIOLET
        b += f'<circle cx="{x}" cy="{y}" r="6" fill="{CARD_BG}" stroke="{color}" stroke-width="2"/>'
        b += (f'<text x="{x + 24}" y="{y + 6}" class="s" font-size="18" font-weight="700" fill="{TEXT}">'
              f'{esc(org)}<tspan class="m" font-size="13" font-weight="500" fill="{color}" dx="12">'
              f'{esc(role)}</tspan></text>\n')
        b += text(x + 24, y + 32, detail, 14, MUTED)
    return svg(W, H, b)


# ─────────────────────────────── README ────────────────────────────────

def readme(ctas):
    focus_alt = f"$ whoami — {WHOAMI}. $ current_focus — " + "; ".join(FOCUS) + f". $ stack — {STACK}"
    skills_alt = " | ".join(f"{g}: {', '.join(items)}" for g, _, items in SKILLS)
    metrics_alt = " · ".join(f"{v} {l}" for v, l, _ in METRICS)
    exp_alt = " | ".join(f"{o} — {r}: {d}" for o, r, d in EXPERIENCE)
    buttons = "\n".join(
        f'  <a href="{esc(url)}"><img src="assets/cta-{icon}.svg" height="34" alt="{esc(label)}" /></a>'
        for label, icon, url in ctas)
    def project_img(p):
        img = (f'<img src="assets/project-{p["slug"]}.svg" width="100%" '
               f'alt="{esc(p["name"])} — {esc(p["desc"])} ({esc(", ".join(p["tags"]))})" />')
        return f'<a href="{esc(p["url"])}">{img}</a>' if p["url"] else img

    projects = "\n\n".join(project_img(p) for p in PROJECTS)
    if SHOW_STATS:
        skills_row = (f'<img src="assets/github-stats.svg" width="49.9%" alt="GitHub stats for @{USERNAME}" />'
                      f'<img src="assets/skills.svg" width="49.9%" alt="{esc(skills_alt)}" />')
        footer = "<sub><code>stats refresh daily via GitHub Actions</code></sub>\n\n"
    else:
        contact_alt = "Contact — " + " · ".join(f"{l}: {v}" for _, l, v in CONTACT)
        skills_row = (f'<a href="{esc(CONTACT_URL)}"><img src="assets/contact.svg" width="49.9%" '
                      f'alt="{esc(contact_alt)}" /></a><img src="assets/skills.svg" width="49.9%" '
                      f'alt="{esc(skills_alt)}" />')
        footer = ""
    # Side-by-side images are written with no whitespace between them so they never wrap.
    return f"""<!-- Generated by scripts/build.py — edit the CONFIG there, not this file. -->

<div align="center">

<img src="assets/header.svg" width="100%" alt="{esc(HERO['headline'])} {esc(HERO['role'])}. {esc(HERO['subtitle'])}" />

<p>
{buttons}
</p>

<img src="assets/current-focus.svg" width="66.6%" alt="{esc(focus_alt)}" /><img src="assets/mascot.svg" width="33.3%" alt="Pixel-art cat coding on a laptop" />

{skills_row}

<img src="assets/metrics.svg" width="100%" alt="{esc(metrics_alt)}" />

<img src="assets/section-projects.svg" width="100%" alt="Featured Projects" />

{projects}

<img src="assets/section-experience.svg" width="100%" alt="Experience" />

<img src="assets/experience.svg" width="100%" alt="{esc(exp_alt)}" />

{footer}</div>
"""


def main():
    offline = "--offline" in sys.argv
    ASSETS.mkdir(exist_ok=True)
    files = {
        "header.svg": header(),
        "current-focus.svg": current_focus(),
        "mascot.svg": mascot(),
        "skills.svg": skills(wide=False),
        "metrics.svg": metrics(),
        "section-projects.svg": section("FEATURED PROJECTS"),
        "section-experience.svg": section("EXPERIENCE"),
        "experience.svg": experience(),
    }
    ctas = [(label, icon, url) for label, icon, url in LINKS if url]
    for label, icon, _ in LINKS:
        files[f"cta-{icon}.svg"] = cta(label, icon)
    for i, p in enumerate(PROJECTS, 1):
        files[f"project-{p['slug']}.svg"] = project(i, p)
    stats_path = ASSETS / "github-stats.svg"
    if not SHOW_STATS:
        stats_path.unlink(missing_ok=True)
        files["contact.svg"] = contact()
    elif not offline:
        try:
            files["github-stats.svg"] = github_stats(fetch_stats())
        except Exception as e:  # keep the last good card rather than failing the whole build
            print(f"warning: stats fetch failed ({e}); keeping existing github-stats.svg", file=sys.stderr)
    if SHOW_STATS and not stats_path.exists() and "github-stats.svg" not in files:
        files["github-stats.svg"] = github_stats([(l, "—", c) for l, c in [
            ("Total Stars", "#d29922"), ("Total Commits", CYAN), ("Total PRs", VIOLET),
            ("Total Issues", "#58a6ff"), ("Contributions", GREEN), ("Current Streak", "#f0883e")]])
    for name, content in files.items():
        (ASSETS / name).write_text(content)
    (ROOT / "README.md").write_text(readme(ctas))
    print(f"wrote {len(files)} assets + README.md")


if __name__ == "__main__":
    main()

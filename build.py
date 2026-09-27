#!/usr/bin/env python3
"""Unspun static news site generator.

Reads editions/<YYYY-MM-DD>/edition.json + stories.json, writes a static
site into site/ ready for GitHub Pages.

stories.json entry:
  {id, slug, headline, dek, body, audio, sources[], }
body: plain text, paragraphs separated by blank lines.
Durations are probed from the mp3 files automatically.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
EDITIONS = os.path.join(ROOT, "editions")
SITE = os.path.join(ROOT, "docs")
STATIC = os.path.join(ROOT, "static")
BASE_URL = "https://phoenixbyrd.github.io/unspun"


def ffprobe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def fmt_duration(secs):
    secs = int(round(secs))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def render_body(body):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    return "\n".join(f"<p>{esc(p)}</p>" for p in paras)


CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#f7f7f5;color:#1a1a1a;line-height:1.65}
a{color:#0b5fff;text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:0 18px}
header.site{background:#111;color:#fff;padding:14px 0;position:sticky;top:0;z-index:10}
header.site .wrap{display:flex;align-items:center;justify-content:space-between}
.brand{font-size:22px;font-weight:800;letter-spacing:.5px;color:#fff}
.brand span{color:#ffd23f}
.tagline{font-size:12px;color:#bbb;margin-top:2px}
nav a{color:#ddd;font-size:14px;margin-left:18px}
.hero{background:#fff;border-bottom:1px solid #e3e3e0;padding:28px 0}
.hero .kicker{font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin-bottom:8px}
.hero h1{font-size:30px;line-height:1.2;margin-bottom:10px}
.hero .desc{color:#444;font-size:16px;margin-bottom:16px}
audio{width:100%;margin:10px 0}
.ep-meta{font-size:13px;color:#777}
.stories{padding:26px 0}
.story-card{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:20px;margin-bottom:18px}
.story-card h2{font-size:21px;line-height:1.3;margin-bottom:6px}
.story-card h2 a{color:#1a1a1a}
.story-card .dek{color:#555;font-size:15px;margin-bottom:10px}
.story-card .meta{font-size:12px;color:#888;margin-top:8px}
article.story{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:26px 22px;margin:22px 0}
article.story h2{font-size:26px;line-height:1.25;margin-bottom:8px}
article.story .dek{font-size:17px;color:#444;margin-bottom:12px}
article.story .byline{font-size:13px;color:#888;margin-bottom:14px}
article.story p{margin-bottom:14px;font-size:16px}
.sources{margin-top:18px;padding-top:14px;border-top:1px solid #eee;font-size:13px;color:#666}
.sources strong{color:#444}
.how{background:#fffbe8;border:1px solid #f0e3a0;border-radius:10px;padding:18px;margin:26px 0;font-size:14px;color:#555}
footer.site{border-top:1px solid #e3e3e0;padding:22px 0;margin-top:30px;font-size:13px;color:#888}
.archive-list{list-style:none;padding:20px 0}
.archive-list li{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:16px 20px;margin-bottom:12px}
.archive-list .d{font-size:13px;color:#888}
"""

HEADER = """<header class="site"><div class="wrap">
<div><a class="brand" href="{base}/">UNSPUN<span>.</span></a><div class="tagline">Just the facts.</div></div>
<nav><a href="{base}/">Today</a><a href="{base}/archive.html">Archive</a></nav>
</div></header>"""

FOOTER = """<footer class="site"><div class="wrap">
Unspun is a daily facts-only newscast. Every story is checked against named sources before publishing. No partisan framing, no spin, no background music.<br>
Questions or corrections: reply in the Muse app.
</div></footer>"""

HOW = """<div class="how"><strong>How we verify.</strong> Every Unspun story is checked against named, published sources before it appears here. Numbers come from the source that reported them. When sources disagree or something is unknown, we say so. We never infer motives or attribute feelings that weren't explicitly stated.</div>"""


def load_edition(date):
    d = os.path.join(EDITIONS, date)
    with open(os.path.join(d, "edition.json")) as f:
        edition = json.load(f)
    with open(os.path.join(d, "stories.json")) as f:
        stories = json.load(f)
    return edition, stories


def build_edition(date):
    edition, stories = load_edition(date)
    src_audio = os.path.join(EDITIONS, date, "audio")
    dst_audio = os.path.join(SITE, "audio", date)
    os.makedirs(dst_audio, exist_ok=True)

    ep_path = os.path.join(src_audio, edition["episode_audio"])
    ep_dur = ffprobe_duration(ep_path)
    shutil.copy2(ep_path, os.path.join(dst_audio, edition["episode_audio"]))

    story_html = []
    cards = []
    for st in stories:
        a_path = os.path.join(src_audio, st["audio"])
        dur = ffprobe_duration(a_path)
        shutil.copy2(a_path, os.path.join(dst_audio, st["audio"]))
        audio_url = f"{BASE_URL}/audio/{date}/{st['audio']}"
        body_html = render_body(st["body"])
        sources = ", ".join(esc(s) for s in st.get("sources", []))
        story_html.append(f"""<article class="story" id="{st['slug']}">
<h2>{esc(st['headline'])}</h2>
<div class="dek">{esc(st['dek'])}</div>
<div class="byline">Unspun &middot; {esc(edition['date_label'])} &middot; Listen: {fmt_duration(dur)}</div>
<audio controls preload="none" src="{audio_url}"></audio>
{body_html}
<div class="sources"><strong>Sources:</strong> {sources}</div>
</article>""")
        cards.append(f"""<div class="story-card">
<h2><a href="{BASE_URL}/editions/{date}/#{st['slug']}">{esc(st['headline'])}</a></h2>
<div class="dek">{esc(st['dek'])}</div>
<audio controls preload="none" src="{audio_url}"></audio>
<div class="meta">Listen: {fmt_duration(dur)} &middot; <a href="{BASE_URL}/editions/{date}/#{st['slug']}">Read the story</a></div>
</div>""")

    ep_url = f"{BASE_URL}/audio/{date}/{edition['episode_audio']}"
    edition_page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(edition['title'])} | Unspun</title>
<link rel="stylesheet" href="{BASE_URL}/static/style.css"></head>
<body>
{HEADER.format(base=BASE_URL)}
<div class="wrap">
<div class="hero" style="background:none;border:none;padding:26px 0 6px">
<div class="kicker">Daily edition &middot; {esc(edition['date_label'])}</div>
<h1>{esc(edition['title'])}</h1>
<div class="desc">{esc(edition['description'])}</div>
<audio controls preload="none" src="{ep_url}"></audio>
<div class="ep-meta">Full episode &middot; {fmt_duration(ep_dur)} &middot; voice only, no music</div>
</div>
{HOW}
{''.join(story_html)}
</div>
{FOOTER}
</body></html>"""

    out_dir = os.path.join(SITE, "editions", date)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(edition_page)
    return edition, stories, ep_dur


def build_index_and_archive(editions_built):
    # editions_built: list of (date, edition, ep_dur), newest first
    date, edition, ep_dur = editions_built[0]
    _, stories = load_edition(date)
    ep_url = f"{BASE_URL}/audio/{date}/{edition['episode_audio']}"
    cards = []
    for st in stories:
        audio_url = f"{BASE_URL}/audio/{date}/{st['audio']}"
        cards.append(f"""<div class="story-card">
<h2><a href="{BASE_URL}/editions/{date}/#{st['slug']}">{esc(st['headline'])}</a></h2>
<div class="dek">{esc(st['dek'])}</div>
<audio controls preload="none" src="{audio_url}"></audio>
</div>""")

    index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unspun | Just the facts.</title>
<link rel="stylesheet" href="{BASE_URL}/static/style.css"></head>
<body>
{HEADER.format(base=BASE_URL)}
<div class="wrap">
<div class="hero">
<div class="kicker">Today's edition &middot; {esc(edition['date_label'])}</div>
<h1>{esc(edition['title'])}</h1>
<div class="desc">{esc(edition['description'])}</div>
<audio controls preload="none" src="{ep_url}"></audio>
<div class="ep-meta">Full episode &middot; {fmt_duration(ep_dur)} &middot; voice only, no music</div>
</div>
{HOW}
<div class="stories">
{''.join(cards)}
</div>
</div>
{FOOTER}
</body></html>"""
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(index)

    items = []
    for d, ed, dur in editions_built:
        items.append(f"""<li><a href="{BASE_URL}/editions/{d}/"><strong>{esc(ed['title'])}</strong></a>
<div class="d">{esc(ed['date_label'])} &middot; full episode {fmt_duration(dur)}</div></li>""")
    archive = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archive | Unspun</title>
<link rel="stylesheet" href="{BASE_URL}/static/style.css"></head>
<body>
{HEADER.format(base=BASE_URL)}
<div class="wrap">
<div class="hero"><div class="kicker">Archive</div><h1>Past editions</h1></div>
<ul class="archive-list">{''.join(items)}</ul>
</div>
{FOOTER}
</body></html>"""
    with open(os.path.join(SITE, "archive.html"), "w") as f:
        f.write(archive)


def main():
    dates = sorted([d for d in os.listdir(EDITIONS)
                    if os.path.isdir(os.path.join(EDITIONS, d))],
                   reverse=True)
    if not dates:
        print("no editions", file=sys.stderr)
        sys.exit(1)
    os.makedirs(SITE, exist_ok=True)
    os.makedirs(os.path.join(SITE, "static"), exist_ok=True)
    with open(os.path.join(SITE, "static", "style.css"), "w") as f:
        f.write(CSS)
    # placeholder to keep dirs in git
    built = []
    for d in dates:
        edition, _, ep_dur = build_edition(d)
        built.append((d, edition, ep_dur))
    build_index_and_archive(built)
    # CNAME-less; .nojekyll for Pages
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    print(f"built {len(built)} edition(s): {', '.join(dates)}")


if __name__ == "__main__":
    main()

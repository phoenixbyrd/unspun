#!/usr/bin/env python3
"""Unspun static NEWS site generator.

Reads editions/<YYYY-MM-DD>/edition.json + stories.json, writes a static
news site into docs/ ready for GitHub Pages.

- Homepage: today's front page (lead broadcast + top stories).
- /editions/<date>/: the day's front page.
- /editions/<date>/<slug>/: each story's own article page with its audio.
- /archive.html: past editions.

stories.json entry:
  {id, slug, headline, dek, body, audio, sources[], order}
body: plain text, paragraphs separated by blank lines.
Durations are probed from the mp3 files automatically.
"""
import json
import os
import re
import shutil
import subprocess
import sys

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
.masthead{background:#fff;border-bottom:2px solid #111;padding:22px 0 16px}
.masthead .dateline{font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin-bottom:6px}
.masthead h1{font-size:34px;line-height:1.15;margin-bottom:8px}
.masthead .standfirst{color:#444;font-size:16px;margin-bottom:14px}
audio{width:100%;margin:10px 0}
.ep-meta{font-size:13px;color:#777}
.broadcast{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:20px;margin:22px 0}
.broadcast .kicker{font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin-bottom:8px}
.broadcast h2{font-size:22px;margin-bottom:8px}
.section-head{font-size:13px;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin:28px 0 12px;border-bottom:2px solid #111;padding-bottom:6px}
.story-lead{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:22px;margin-bottom:14px}
.story-lead h2{font-size:24px;line-height:1.25;margin-bottom:6px}
.story-lead h2 a,.story-row h3 a{color:#1a1a1a}
.story-row{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:16px 20px;margin-bottom:12px}
.story-row h3{font-size:19px;line-height:1.3;margin-bottom:4px}
.dek{color:#555;font-size:15px;margin-bottom:8px}
.meta{font-size:12px;color:#888;margin-top:6px}
article.story{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:26px 22px;margin:22px 0}
article.story h1{font-size:28px;line-height:1.25;margin-bottom:8px}
article.story .dek{font-size:17px;color:#444;margin-bottom:12px}
article.story .byline{font-size:13px;color:#888;margin-bottom:14px}
article.story p{margin-bottom:14px;font-size:16px}
.sources{margin-top:18px;padding-top:14px;border-top:1px solid #eee;font-size:13px;color:#666}
.sources strong{color:#444}
.story-nav{display:flex;justify-content:space-between;margin:24px 0;font-size:14px}
.how{background:#fffbe8;border:1px solid #f0e3a0;border-radius:10px;padding:18px;margin:26px 0;font-size:14px;color:#555}
footer.site{border-top:1px solid #e3e3e0;padding:22px 0;margin-top:30px;font-size:13px;color:#888}
.archive-list{list-style:none;padding:20px 0}
.archive-list li{background:#fff;border:1px solid #e6e6e3;border-radius:10px;padding:16px 20px;margin-bottom:12px}
.archive-list .d{font-size:13px;color:#888}
"""

HEADER = """<header class="site"><div class="wrap">
<div><a class="brand" href="{base}/">UNSPUN<span>.</span></a><div class="tagline">Just the facts.</div></div>
<nav><a href="{base}/">Front page</a><a href="{base}/archive.html">Archive</a></nav>
</div></header>"""

FOOTER = """<footer class="site"><div class="wrap">
Unspun is a daily facts-only newscast. Every story is checked against named sources before publishing. No partisan framing, no spin, no background music.<br>
Questions or corrections: reply in the Muse app.
</div></footer>"""

HOW = """<div class="how"><strong>How we verify.</strong> Every Unspun story is checked against named, published sources before it appears here. Numbers come from the source that reported them. When sources disagree or something is unknown, we say so. We never infer motives or attribute feelings that weren't explicitly stated.</div>"""

PAGE_TOP = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Unspun</title>
<link rel="stylesheet" href="{base}/static/style.css"></head>
<body>
"""


def load_edition(date):
    d = os.path.join(EDITIONS, date)
    with open(os.path.join(d, "edition.json")) as f:
        edition = json.load(f)
    with open(os.path.join(d, "stories.json")) as f:
        stories = json.load(f)
    return edition, stories


def build_edition(date):
    edition, stories = load_edition(date)
    stories = sorted(stories, key=lambda s: s.get("order", 0))
    src_audio = os.path.join(EDITIONS, date, "audio")
    dst_audio = os.path.join(SITE, "audio", date)
    os.makedirs(dst_audio, exist_ok=True)

    ep_path = os.path.join(src_audio, edition["episode_audio"])
    ep_dur = ffprobe_duration(ep_path)
    shutil.copy2(ep_path, os.path.join(dst_audio, edition["episode_audio"]))
    ep_url = f"{BASE_URL}/audio/{date}/{edition['episode_audio']}"

    story_infos = []
    for st in stories:
        a_path = os.path.join(src_audio, st["audio"])
        dur = ffprobe_duration(a_path)
        shutil.copy2(a_path, os.path.join(dst_audio, st["audio"]))
        story_infos.append({**st, "dur": dur,
                            "url": f"{BASE_URL}/editions/{date}/{st['slug']}/",
                            "audio_url": f"{BASE_URL}/audio/{date}/{st['audio']}"})

    out_dir = os.path.join(SITE, "editions", date)
    os.makedirs(out_dir, exist_ok=True)

    # Per-story article pages
    for i, st in enumerate(story_infos):
        sources = ", ".join(esc(s) for s in st.get("sources", []))
        nav = []
        if i > 0:
            p = story_infos[i - 1]
            nav.append(f'<a href="{p["url"]}">&larr; {esc(p["headline"])}</a>')
        else:
            nav.append(f'<a href="{BASE_URL}/editions/{date}/">&larr; Front page</a>')
        if i < len(story_infos) - 1:
            n = story_infos[i + 1]
            nav.append(f'<a href="{n["url"]}">{esc(n["headline"])} &rarr;</a>')
        else:
            nav.append(f'<a href="{BASE_URL}/editions/{date}/">Front page &rarr;</a>')
        page = (PAGE_TOP.format(title=st["headline"], base=BASE_URL)
                + HEADER.format(base=BASE_URL) + f"""
<div class="wrap">
<article class="story">
<div class="dateline" style="font-size:12px;text-transform:uppercase;letter-spacing:1.5px;color:#888;margin-bottom:8px">Unspun &middot; {esc(edition['date_label'])}</div>
<h1>{esc(st['headline'])}</h1>
<div class="dek">{esc(st['dek'])}</div>
<div class="byline">Unspun &middot; Listen: {fmt_duration(st['dur'])}</div>
<audio controls preload="none" src="{st['audio_url']}"></audio>
{render_body(st['body'])}
<div class="sources"><strong>Sources:</strong> {sources}</div>
</article>
<div class="story-nav">{' '.join(f'<span>{x}</span>' for x in nav)}</div>
</div>
{FOOTER}
</body></html>""")
        sdir = os.path.join(out_dir, st["slug"])
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "index.html"), "w") as f:
            f.write(page)

    # Day's front page
    lead = story_infos[0]
    rows = []
    for st in story_infos[1:]:
        rows.append(f"""<div class="story-row">
<h3><a href="{st['url']}">{esc(st['headline'])}</a></h3>
<div class="dek">{esc(st['dek'])}</div>
<audio controls preload="none" src="{st['audio_url']}"></audio>
<div class="meta">Listen: {fmt_duration(st['dur'])}</div>
</div>""")
    edition_page = (PAGE_TOP.format(title=edition["title"], base=BASE_URL)
                    + HEADER.format(base=BASE_URL) + f"""
<div class="wrap">
<div class="masthead">
<div class="dateline">{esc(edition['date_label'])} &middot; Daily edition</div>
<h1>{esc(edition['title'])}</h1>
<div class="standfirst">{esc(edition['description'])}</div>
</div>
<div class="broadcast">
<div class="kicker">Today's broadcast</div>
<h2>Listen to the full newscast</h2>
<audio controls preload="none" src="{ep_url}"></audio>
<div class="ep-meta">Full episode &middot; {fmt_duration(ep_dur)} &middot; voice only, no music</div>
</div>
{HOW}
<div class="section-head">Top stories</div>
<div class="story-lead">
<h2><a href="{lead['url']}">{esc(lead['headline'])}</a></h2>
<div class="dek">{esc(lead['dek'])}</div>
<audio controls preload="none" src="{lead['audio_url']}"></audio>
<div class="meta">Listen: {fmt_duration(lead['dur'])} &middot; <a href="{lead['url']}">Read the story</a></div>
</div>
{''.join(rows)}
</div>
{FOOTER}
</body></html>""")
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(edition_page)
    return edition, story_infos, ep_dur


def build_index_and_archive(editions_built):
    # editions_built: list of (date, edition, story_infos, ep_dur), newest first
    date, edition, story_infos, ep_dur = editions_built[0]
    ep_url = f"{BASE_URL}/audio/{date}/{edition['episode_audio']}"
    lead = story_infos[0]
    rows = []
    for st in story_infos[1:]:
        rows.append(f"""<div class="story-row">
<h3><a href="{st['url']}">{esc(st['headline'])}</a></h3>
<div class="dek">{esc(st['dek'])}</div>
<audio controls preload="none" src="{st['audio_url']}"></audio>
<div class="meta">Listen: {fmt_duration(st['dur'])}</div>
</div>""")
    index = (PAGE_TOP.format(title="Just the facts.", base=BASE_URL)
             + HEADER.format(base=BASE_URL) + f"""
<div class="wrap">
<div class="masthead">
<div class="dateline">{esc(edition['date_label'])} &middot; Latest</div>
<h1>Unspun</h1>
<div class="standfirst">{esc(edition['description'])}</div>
</div>
<div class="broadcast">
<div class="kicker">Today's broadcast</div>
<h2>{esc(edition['title'])}</h2>
<audio controls preload="none" src="{ep_url}"></audio>
<div class="ep-meta">Full episode &middot; {fmt_duration(ep_dur)} &middot; voice only, no music</div>
</div>
<div class="section-head">Top stories</div>
<div class="story-lead">
<h2><a href="{lead['url']}">{esc(lead['headline'])}</a></h2>
<div class="dek">{esc(lead['dek'])}</div>
<audio controls preload="none" src="{lead['audio_url']}"></audio>
<div class="meta">Listen: {fmt_duration(lead['dur'])} &middot; <a href="{lead['url']}">Read the story</a></div>
</div>
{''.join(rows)}
</div>
{FOOTER}
</body></html>""")
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(index)

    items = []
    for d, ed, _, dur in editions_built:
        items.append(f"""<li><a href="{BASE_URL}/editions/{d}/"><strong>{esc(ed['title'])}</strong></a>
<div class="d">{esc(ed['date_label'])} &middot; full episode {fmt_duration(dur)}</div></li>""")
    archive = (PAGE_TOP.format(title="Archive", base=BASE_URL)
               + HEADER.format(base=BASE_URL) + f"""
<div class="wrap">
<div class="masthead"><div class="dateline">Archive</div><h1>Past editions</h1></div>
<ul class="archive-list">{''.join(items)}</ul>
</div>
{FOOTER}
</body></html>""")
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
    built = []
    for d in dates:
        edition, story_infos, ep_dur = build_edition(d)
        built.append((d, edition, story_infos, ep_dur))
    build_index_and_archive(built)
    open(os.path.join(SITE, ".nojekyll"), "w").close()
    print(f"built {len(built)} edition(s): {', '.join(dates)}")


if __name__ == "__main__":
    main()

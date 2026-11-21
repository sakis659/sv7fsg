#!/usr/bin/env python3
"""
Φτιάχνει από το news.json:
  - μία σελίδα για κάθε είδηση:  dx/<slug>/index.html
  - dx/index.html (λίστα όλων)
  - feed.xml (RSS), sitemap.xml, robots.txt
Τρέξε:  python3 build.py
"""
import json, os, re, shutil, html, unicodedata, datetime as dt
from email.utils import format_datetime

SITE = "https://sv7fsg-radio.pages.dev"     # ✏️ άλλαξέ το αν πάρεις δικό σου domain
CALL = "SV7FSG"
ROOT = os.path.dirname(os.path.abspath(__file__))
TYPES = {"dxpedition": "DXpedition", "special": "Special event station", "dx": "DX activity",
         "contest": "Contest", "satellite": "Satellites / ISS", "news": "News"}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
e = lambda s: html.escape(str(s or ""), quote=True)


def slugify(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = t.lower().replace("/", "-")
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return re.sub(r"-+", "-", t).strip("-")[:80]


def make_slug(n):
    year = (n.get("start") or n.get("added") or "")[:4]
    place = re.sub(r"\(.*?\)", "", n.get("entity_en") or n.get("entity") or "")
    if n.get("type") == "contest":
        place = ""
    return slugify(f"{n.get('call') or n.get('title')} {place} {year}")


def pdate(s):
    return dt.date.fromisoformat(s) if s else None


def fdate(d):
    return f"{d.day} {MONTHS[d.month-1]} {d.year}" if d else ""


def dates_text(n):
    s, en = pdate(n.get("start")), pdate(n.get("end"))
    if not s:
        return ""
    t = fdate(s) + (f" – {fdate(en)}" if en and en != s else "")
    return ("approx. " if n.get("approx") else "") + t


def title_of(n):
    call = n.get("call") or n.get("title")
    ent = re.sub(r"\s*\(.*?\)", "", n.get("entity_en") or n.get("entity") or "").strip()
    year = (n.get("start") or n.get("added") or "")[:4]
    if n.get("type") == "contest":
        return f"{call} {year}: dates, bands & DXpeditions to work"
    head = f"{call} {ent} {year}" if ent else f"{call} {year}"
    return f"{head}: dates, bands, QSL info"


CSS = """
:root{--bg:#070b14;--bg2:#0c1322;--panel:#101a2d;--line:#1d2a44;--text:#e6edf7;--muted:#8b9ab3;--amber:#ffb547;--green:#38e8c6;
--mono:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.65;
background-image:radial-gradient(ellipse at 80% -10%,#12305a55 0%,transparent 55%)}
a{color:var(--green)}
.wrap{max-width:860px;margin:0 auto;padding:0 22px}
nav{border-bottom:1px solid var(--line);background:#070b14d9}
nav .wrap{display:flex;justify-content:space-between;align-items:center;height:60px}
.logo{font-family:var(--mono);font-weight:700;letter-spacing:.08em;color:var(--text);text-decoration:none}
nav .links a{color:var(--muted);text-decoration:none;margin-left:18px;font-size:.92rem}
.crumbs{font-family:var(--mono);font-size:.78rem;color:var(--muted);margin:34px 0 14px}
.crumbs a{color:var(--muted)}
.type{display:inline-block;font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;padding:4px 10px;border-radius:6px;
background:#ffb5471a;color:var(--amber);border:1px solid #ffb54740}
.status{display:inline-block;margin-left:8px;font-family:var(--mono);font-size:.72rem;padding:4px 10px;border-radius:6px}
.status.live{background:var(--green);color:#04211b;font-weight:700}.status.soon{color:var(--green);border:1px solid #38e8c655}
.status.done{color:var(--muted);border:1px solid var(--line)}
h1{font-family:var(--mono);font-size:clamp(2.2rem,7vw,3.6rem);line-height:1.05;margin:14px 0 6px;text-shadow:0 0 24px #38e8c644}
.sub{color:var(--muted);font-size:1.1rem;margin-bottom:26px}
.grid{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:28px}
.grid div{flex:1 1 170px;background:var(--bg2);padding:16px 18px}
.grid small{display:block;font-family:var(--mono);font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.grid b{font-family:var(--mono);font-weight:600}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:24px;margin-bottom:18px}
.card h2{font-size:1.05rem;margin-bottom:8px}
.card p{color:#c3cde0}
.src li{margin:6px 0 6px 18px}
.more{list-style:none;display:grid;gap:8px}
.more a{display:flex;justify-content:space-between;gap:10px;padding:12px 16px;border:1px solid var(--line);border-radius:10px;background:var(--bg2);text-decoration:none;color:var(--text)}
.more span{color:var(--muted);font-family:var(--mono);font-size:.8rem}
.note{font-size:.85rem;color:var(--muted)}
footer{margin:60px 0 30px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:.88rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
footer .s{font-family:var(--mono);color:var(--amber)}
"""

STATUS_JS = """<script>
(function(){var el=document.getElementById('st');if(!el)return;
var s=el.dataset.s,e=el.dataset.e||s;if(!s)return;var t=new Date();t.setUTCHours(0,0,0,0);
var S=new Date(s+'T00:00:00Z'),E=new Date(e+'T00:00:00Z');
if(E<t){el.className='status done';el.textContent='Completed';}
else if(S<=t){el.className='status live';el.textContent='\\u25CF Active now';}
else{var d=Math.round((S-t)/864e5);el.className='status soon';el.textContent=d===1?'Starts tomorrow':'Starts in '+d+' days';}
el.hidden=false;})();
</script>"""


def head(title, desc, url, extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<link rel="alternate" type="application/rss+xml" title="{CALL} DX News" href="{SITE}/feed.xml">
<meta property="og:type" content="article"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(url)}">
<meta property="og:site_name" content="{CALL}">
<meta property="og:image" content="{SITE}/assets/og-dx.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{CALL} DX News">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/assets/og-dx.jpg">
<link rel="icon" href="/favicon.svg">
<link rel="stylesheet" href="/assets/dx.css">
{extra}
</head>
<body>
<nav><div class="wrap"><a class="logo" href="/">{CALL}</a>
<div class="links"><a href="/dx/">DX News</a><a href="https://www.youtube.com/@SV7FSG" target="_blank" rel="noopener">YouTube</a><a href="https://www.instagram.com/sv7fsg/" target="_blank" rel="noopener">Instagram</a><a href="/#about">Station</a><a href="/#contact">Contact</a></div></div></nav>
<main class="wrap">"""


FOOT = f"""</main>
<div class="wrap"><footer><span>© {dt.date.today().year} {CALL} · Amateur radio station · Xanthi, Greece</span>
<span><a href="https://www.youtube.com/@SV7FSG" target="_blank" rel="noopener">YouTube</a> · <a href="https://www.instagram.com/sv7fsg/" target="_blank" rel="noopener">Instagram</a> · <span class="s">73 DE {CALL}</span></span></footer></div>
</body></html>
"""


def page(n, others):
    url = f"{SITE}/dx/{n['slug']}/"
    title = title_of(n)
    summary = n.get("summary_en") or n.get("summary") or ""
    ent = n.get("entity_en") or n.get("entity") or ""
    dtxt = dates_text(n)
    desc = (f"{n.get('call')} {ent}" + (f", {dtxt}" if dtxt else "") + ". " + summary)[:300]
    ld = {"@context": "https://schema.org", "@type": "Event", "name": f"{n.get('call')} – {ent}".strip(" –"),
          "description": summary, "url": url, "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
          "location": {"@type": "VirtualLocation", "url": url},
          "organizer": {"@type": "Organization", "name": n.get("call") or ""}}
    if n.get("start"): ld["startDate"] = n["start"]
    if n.get("end"): ld["endDate"] = n["end"]
    extra = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"
    rows = [("Dates (UTC)", dtxt or "TBA"), ("Location", ent or "—"),
            ("Bands", " · ".join(n.get("bands") or []) or "—"), ("Modes", " · ".join(n.get("modes") or []) or "—"),
            ("QSL", n.get("qsl") or "See sources")]
    out = [head(f"{title} | {CALL}", desc, url, extra)]
    out.append(f'<div class="crumbs"><a href="/">Home</a> / <a href="/dx/">DX News</a> / {e(n.get("call"))}</div>')
    out.append(f'<span class="type">{e(TYPES.get(n.get("type"), n.get("type")))}</span>'
               f'<span id="st" class="status" data-s="{e(n.get("start"))}" data-e="{e(n.get("end"))}" hidden></span>')
    out.append(f'<h1>{e(n.get("call") or n.get("title"))}</h1><p class="sub">{e(ent)}</p>')
    out.append('<div class="grid">' + "".join(f"<div><small>{e(k)}</small><b>{e(v)}</b></div>" for k, v in rows) + "</div>")
    out.append(f'<section class="card"><h2>Summary</h2><p>{e(summary)}</p></section>')
    if n.get("summary") and n.get("summary_en"):
        out.append(f'<section class="card" lang="el"><h2>Στα ελληνικά</h2><p>{e(n["summary"])}</p></section>')
    srcs = "".join(f'<li><a href="{e(s.get("url"))}" target="_blank" rel="noopener">{e(s.get("name"))}</a></li>'
                   for s in n.get("sources") or [])
    out.append(f'<section class="card"><h2>Sources</h2><ul class="src">{srcs}</ul>'
               f'<p class="note">Summary written by {CALL}. Always check the official source for the latest schedule and QSL details.</p></section>')
    if others:
        li = "".join(f'<li><a href="/dx/{o["slug"]}/">{e(o.get("call"))} · {e(o.get("entity_en") or o.get("entity"))}'
                     f'<span>{e(dates_text(o))}</span></a></li>' for o in others[:6])
        out.append(f'<section class="card"><h2>More DX on the air</h2><ul class="more">{li}</ul></section>')
    out.append(STATUS_JS + FOOT)
    return "".join(out)


def index_page(items):
    url = f"{SITE}/dx/"
    li = "".join(f'<li><a href="/dx/{n["slug"]}/">{e(n.get("call"))} · {e(n.get("entity_en") or n.get("entity"))}'
                 f'<span>{e(dates_text(n))}</span></a></li>' for n in items)
    return (head(f"DX News: DXpeditions, special calls & contests | {CALL}",
                 "Current and upcoming DXpeditions, special event stations and contests, with dates, bands and QSL info. Curated by SV7FSG.", url)
            + '<div class="crumbs"><a href="/">Home</a> / DX News</div>'
            + '<h1>DX News</h1><p class="sub">DXpeditions, special event stations and contests, with dates, bands and QSL info. '
              f'Also available as an <a href="/feed.xml">RSS feed</a>.</p>'
            + f'<section class="card"><ul class="more">{li}</ul></section>' + FOOT)


def rss(items):
    now = format_datetime(dt.datetime.now(dt.timezone.utc))
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f"<title>{CALL} DX News</title><link>{SITE}/dx/</link>",
           "<description>DXpeditions, special event stations and contests, with dates, bands and QSL info.</description>",
           f'<language>en</language><lastBuildDate>{now}</lastBuildDate><atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>']
    for n in sorted(items, key=lambda x: x.get("added") or "", reverse=True)[:50]:
        u = f"{SITE}/dx/{n['slug']}/"
        added = dt.datetime.fromisoformat((n.get("added") or "2026-01-01") + "T06:00:00+00:00")
        d = dates_text(n)
        desc = (f"[{d}] " if d else "") + (n.get("summary_en") or n.get("summary") or "")
        out.append(f"<item><title>{e(title_of(n))}</title><link>{u}</link><guid isPermaLink=\"true\">{u}</guid>"
                   f"<pubDate>{format_datetime(added)}</pubDate><description>{e(desc)}</description></item>")
    out.append("</channel></rss>\n")
    return "".join(out)


def main():
    p = os.path.join(ROOT, "news.json")
    data = json.load(open(p, encoding="utf-8"))
    items = data.get("items", [])
    used = set()
    for n in items:
        if not n.get("slug"):
            n["slug"] = make_slug(n)
        base, i = n["slug"], 2
        while n["slug"] in used:
            n["slug"] = f"{base}-{i}"; i += 1
        used.add(n["slug"])
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(p, "a", encoding="utf-8").write("\n")

    today = dt.date.today()
    def active(n):
        end = pdate(n.get("end")) or pdate(n.get("start"))
        return not end or end >= today
    order = sorted(items, key=lambda n: (not active(n), n.get("start") or n.get("added") or ""))

    dxdir = os.path.join(ROOT, "dx")
    if os.path.isdir(dxdir):
        shutil.rmtree(dxdir)
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    open(os.path.join(ROOT, "assets", "dx.css"), "w").write(CSS.strip() + "\n")
    for n in items:
        d = os.path.join(dxdir, n["slug"]); os.makedirs(d, exist_ok=True)
        others = [o for o in order if o is not n and active(o)]
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page(n, others))
    open(os.path.join(dxdir, "index.html"), "w", encoding="utf-8").write(index_page(order))
    open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8").write(rss(items))

    urls = [(f"{SITE}/", data.get("updated")), (f"{SITE}/dx/", data.get("updated"))]
    urls += [(f"{SITE}/dx/{n['slug']}/", n.get("added")) for n in items]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>" for u, m in urls]
    sm.append("</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(sm))
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"OK: {len(items)} σελίδες, feed.xml, sitemap.xml")


if __name__ == "__main__":
    main()

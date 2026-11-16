#!/usr/bin/env python3
"""
Υλικό για social media από το news.json.

  python3 social.py cards [id ...]   → social/out/cards/<slug>.png  (1080x1350, Instagram/Facebook)
                                       + <slug>.txt (κείμενο + hashtags)
  python3 social.py short            → social/out/short-ΕΕΕΕ-ΜΜ-ΗΗ.mp4 (1080x1920, YouTube Shorts / Reels)
                                       + .txt (τίτλος, περιγραφή, hashtags)

Χωρίς id, οι κάρτες φτιάχνονται για τις ειδήσεις που προστέθηκαν σήμερα.
Τα αρχεία στο social/out δεν μπαίνουν στο git (.gitignore). Στέλνονται στον χρήστη για έγκριση.
Χρειάζεται: python3, playwright (chromium), ffmpeg, numpy.
"""
import json, os, re, sys, html, subprocess, shutil, wave, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "social", "out")
SITE_SHORT = "sv7fsg-radio.pages.dev"
CALL = "SV7FSG"
TYPES = {"dxpedition": "DXpedition", "special": "Special event", "dx": "DX activity",
         "contest": "Contest", "satellite": "Satellites / ISS", "news": "News"}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
e = lambda s: html.escape(str(s or ""))
FPS = 30

FONTS = """
:root{--bg:#070b14;--panel:#101a2d;--line:#1d2a44;--text:#e6edf7;--muted:#8b9ab3;--amber:#ffb547;--green:#38e8c6}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:Inter,"DejaVu Sans",system-ui,sans-serif;overflow:hidden}
.mono{font-family:"DejaVu Sans Mono",ui-monospace,Menlo,monospace}
.bgfx{position:absolute;inset:0;background:
 radial-gradient(ellipse at 85% -5%,#12305a 0%,transparent 55%),
 radial-gradient(ellipse at -10% 60%,#0e3b3a88 0%,transparent 50%),var(--bg)}
.wf{position:absolute;left:0;right:0;height:180px;opacity:.55;
 background:repeating-linear-gradient(90deg,transparent 0 38px,#38e8c622 38px 40px),
 linear-gradient(180deg,#0a2a6e55,#02050b00)}
.rings{position:absolute;border-radius:50%;border:2px solid #38e8c633}
"""


def pdate(s): return dt.date.fromisoformat(s) if s else None
def fdate(d): return f"{d.day} {MONTHS[d.month-1]}" if d else ""


def dates_text(n, year=True):
    s, en = pdate(n.get("start")), pdate(n.get("end"))
    if not s: return "Dates TBA"
    t = fdate(s) + (f" – {fdate(en)}" if en and en != s else "") + (f" {(en or s).year}" if year else "")
    return ("≈ " if n.get("approx") else "") + t


def status(n, today):
    s, en = pdate(n.get("start")), pdate(n.get("end")) or pdate(n.get("start"))
    if not s: return ("", "")
    if en < today: return ("done", "Completed")
    if s <= today: return ("live", "● ON THE AIR NOW")
    d = (s - today).days
    return ("soon", "Starts tomorrow" if d == 1 else f"Starts in {d} days")


def short_summary(t, limit=190):
    t = t or ""
    if len(t) <= limit: return t
    cut = t[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def hashtags(n):
    tags = ["#hamradio", "#amateurradio", "#DX", "#DXpedition" if n.get("type") == "dxpedition" else "#DXing",
            "#" + re.sub(r"[^A-Za-z0-9]", "", n.get("call") or ""), "#" + CALL]
    if "FT8" in (n.get("modes") or []): tags.append("#FT8")
    if "CW" in (n.get("modes") or []): tags.append("#CW")
    if n.get("type") == "contest": tags.append("#contesting")
    ent = re.sub(r"\(.*?\)", "", n.get("entity_en") or "")
    if ent.strip() and n.get("type") != "contest": tags.append("#" + re.sub(r"[^A-Za-z0-9]", "", ent.title()))
    return " ".join(dict.fromkeys(tags))


# ---------- HTML templates ----------
def card_html(n, w, h, today, idx=None, total=None):
    st_cls, st_txt = status(n, today)
    st_style = {"live": "background:#38e8c6;color:#04211b;font-weight:700",
                "soon": "border:3px solid #38e8c688;color:#38e8c6",
                "done": "border:3px solid #1d2a44;color:#8b9ab3"}.get(st_cls, "display:none")
    tall = h > w * 1.5
    call = n.get("call") or n.get("title") or ""
    csize = 190 if len(call) <= 6 else 150 if len(call) <= 9 else 112 if len(call) <= 13 else 92
    if tall: csize = int(csize * 1.1)
    ent = n.get("entity_en") or n.get("entity") or ""
    bands = " · ".join(n.get("bands") or []) or "—"
    modes = " · ".join(n.get("modes") or []) or "—"
    src = ", ".join(s.get("name", "") for s in n.get("sources") or [])
    counter = f'<div class="mono" style="font-size:34px;color:#8b9ab3">{idx}/{total}</div>' if idx else ""
    top = 140 if tall else 70
    return f"""<html><head><style>{FONTS}
.wrap{{position:absolute;inset:0;padding:{top}px 80px 80px;display:flex;flex-direction:column}}
.bar{{display:flex;justify-content:space-between;align-items:center}}
.brand{{font-size:38px;font-weight:700;letter-spacing:.12em}} .brand span{{color:var(--amber)}}
.chip{{font-size:30px;letter-spacing:.12em;text-transform:uppercase;padding:10px 22px;border-radius:12px;background:#ffb5471f;color:var(--amber);border:3px solid #ffb54755}}
.st{{font-size:30px;padding:10px 22px;border-radius:12px;{st_style}}}
.call{{font-size:{csize}px;font-weight:800;line-height:1;letter-spacing:.02em;margin-top:{60 if tall else 40}px;text-shadow:0 0 50px #38e8c666}}
.ent{{font-size:{50 if tall else 44}px;color:#c3cde0;margin-top:22px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:3px;background:var(--line);border:3px solid var(--line);border-radius:26px;overflow:hidden;margin-top:{60 if tall else 44}px}}
.grid div{{background:#0c1322;padding:26px 30px}}
.grid small{{display:block;font-size:24px;letter-spacing:.16em;color:var(--muted);text-transform:uppercase;margin-bottom:8px}}
.grid b{{font-size:{40 if tall else 36}px;font-weight:600}}
.grid .full{{grid-column:1 / -1}}
.sum{{font-size:{40 if tall else 34}px;line-height:1.45;color:#c3cde0;margin-top:{50 if tall else 36}px}}
.foot{{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;font-size:28px;color:var(--muted)}}
.url{{font-size:{38 if tall else 32}px;color:var(--green);font-weight:600;white-space:nowrap}}
.foot>div:first-child{{max-width:52%}}
</style></head><body>
<div class="bgfx"></div><div class="wf" style="top:0"></div>
<div class="rings" style="width:900px;height:900px;right:-420px;top:-380px"></div>
<div class="rings" style="width:600px;height:600px;right:-270px;top:-230px;border-color:#ffb54733"></div>
<div class="wrap">
 <div class="bar"><div class="brand mono">{CALL}<span> · DX NEWS</span></div>{counter}</div>
 <div style="display:flex;gap:18px;margin-top:{70 if tall else 50}px;flex-wrap:wrap">
   <span class="chip mono">{e(TYPES.get(n.get('type'), n.get('type')))}</span><span class="st mono">{e(st_txt)}</span></div>
 <div class="call mono">{e(call)}</div>
 <div class="ent">{e(ent)}</div>
 <div class="grid mono">
   <div class="full"><small>Dates (UTC)</small><b>{e(dates_text(n))}</b></div>
   <div><small>Bands</small><b>{e(bands)}</b></div><div><small>Modes</small><b>{e(modes)}</b></div>
   {f'<div class="full"><small>QSL</small><b>{e(n.get("qsl"))}</b></div>' if n.get("qsl") else ''}
 </div>
 <p class="sum">{e(short_summary(n.get('summary_en') or n.get('summary'), 230 if tall else 190))}</p>
 <div class="foot"><div>Source: {e(src)}</div><div class="url mono">{SITE_SHORT}</div></div>
</div></body></html>"""


def intro_html(w, h, today, n_items):
    end = today + dt.timedelta(days=7)
    return f"""<html><head><style>{FONTS}
.c{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}
</style></head><body><div class="bgfx"></div><div class="wf" style="top:0"></div><div class="wf" style="bottom:0;transform:scaleY(-1)"></div>
<div class="rings" style="width:1300px;height:1300px;left:-110px;top:310px"></div>
<div class="rings" style="width:900px;height:900px;left:90px;top:510px;border-color:#ffb54744"></div>
<div class="rings" style="width:520px;height:520px;left:280px;top:700px"></div>
<div class="c">
 <div class="mono" style="font-size:44px;letter-spacing:.3em;color:#ffb547">THIS WEEK IN</div>
 <div class="mono" style="font-size:300px;font-weight:800;line-height:1;text-shadow:0 0 70px #38e8c688">DX</div>
 <div class="mono" style="font-size:46px;color:#c3cde0;margin-top:30px">{fdate(today)} – {fdate(end)} {end.year}</div>
 <div style="font-size:40px;color:#8b9ab3;margin-top:70px">{n_items} stations to put in your log</div>
 <div class="mono" style="font-size:56px;font-weight:700;letter-spacing:.12em;margin-top:120px">{CALL}</div>
</div></body></html>"""


def outro_html(w, h):
    return f"""<html><head><style>{FONTS}
.c{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 80px}}
</style></head><body><div class="bgfx"></div><div class="wf" style="top:0"></div>
<div class="c">
 <div style="font-size:54px;color:#c3cde0;line-height:1.4">Full details, bands &amp; QSL info</div>
 <div class="mono" style="font-size:62px;color:#38e8c6;font-weight:700;margin-top:40px">{SITE_SHORT}</div>
 <div style="font-size:40px;color:#8b9ab3;margin-top:80px">Follow for weekly DX news</div>
 <div class="mono" style="font-size:150px;font-weight:800;color:#ffb547;margin-top:120px;text-shadow:0 0 60px #ffb54766">73</div>
 <div class="mono" style="font-size:52px;letter-spacing:.14em;margin-top:20px">DE {CALL}</div>
</div></body></html>"""


def render_pngs(jobs):
    """jobs: list of (html, path, w, h)"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": jobs[0][2], "height": jobs[0][3]})
        for h_, path, w, h in jobs:
            pg.set_viewport_size({"width": w, "height": h})
            pg.set_content(h_); pg.wait_for_timeout(150)
            pg.screenshot(path=path)
        b.close()


# ---------- CW audio ----------
MORSE = {**dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", ".- -... -.-. -.. . ..-. --. .... .. .--- -.- .-.. -- -. --- .--. --.- .-. ... - ..- ...- .-- -..- -.-- --..".split())),
         **dict(zip("0123456789", "----- .---- ..--- ...-- ....- ..... -.... --... ---.. ----.".split())), "/": "-..-."}
SR = 44100


def cw(text, wpm=24, f=650):
    dot = 1.2 / wpm
    parts = []
    def tone(d):
        t = np.arange(int(SR * d)) / SR
        env = np.minimum(1, np.minimum(t, d - t) / 0.005)
        return 0.35 * np.sin(2 * np.pi * f * t) * env
    sil = lambda d: np.zeros(int(SR * d))
    for word in text.upper().split():
        for ch in word:
            code = MORSE.get(ch)
            if not code: continue
            for s in code:
                parts += [tone(dot if s == "." else 3 * dot), sil(dot)]
            parts.append(sil(2 * dot))
        parts.append(sil(4 * dot))
    return np.concatenate(parts) if parts else np.zeros(1)


def ff(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args, check=True)


def still_clip(png, dur, out, fade_in=True):
    tmp = out[:-4] + ".tmp.mp4"
    vf = f"format=yuv420p,loop=-1:1,trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    if fade_in: vf += ",fade=t=in:st=0:d=0.35"
    vf += f",fade=t=out:st={dur-0.3:.3f}:d=0.3"
    ff(["-framerate", str(FPS), "-i", png, "-vf", vf, "-r", str(FPS), "-c:v", "libx264", "-crf", "20",
        "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp])
    os.replace(tmp, out)


# ---------- commands ----------
def load():
    return json.load(open(os.path.join(ROOT, "news.json"), encoding="utf-8"))


def cmd_cards(ids):
    data = load(); today = dt.date.today()
    items = data["items"]
    sel = [n for n in items if n["id"] in ids] if ids else [n for n in items if n.get("added") == today.isoformat()]
    if not sel:
        print("Καμία είδηση για κάρτα."); return []
    d = os.path.join(OUT, "cards"); os.makedirs(d, exist_ok=True)
    jobs, outs = [], []
    for n in sel:
        slug = n.get("slug") or n["id"]
        png = os.path.join(d, f"{slug}.png")
        jobs.append((card_html(n, 1080, 1350, today), png, 1080, 1350))
        cap = (f"📡 {n.get('call')} – {n.get('entity_en') or ''}\n🗓 {dates_text(n)}\n"
               f"📻 {' · '.join(n.get('bands') or []) or '—'} | {' · '.join(n.get('modes') or []) or '—'}\n\n"
               f"{n.get('summary_en') or n.get('summary')}\n\n"
               f"Full details & QSL info: {SITE_SHORT}/dx/{slug}/\n"
               f"Source: {', '.join(s.get('name','') for s in n.get('sources') or [])}\n\n{hashtags(n)}\n")
        open(png[:-4] + ".txt", "w", encoding="utf-8").write(cap)
        outs.append(png)
    render_pngs(jobs)
    for o in outs: print(o)
    return outs


def cmd_short():
    data = load(); today = dt.date.today()
    horizon = today + dt.timedelta(days=7)
    def ok(n):
        s, en = pdate(n.get("start")), pdate(n.get("end")) or pdate(n.get("start"))
        return s and en >= today and s <= horizon
    items = sorted([n for n in data["items"] if ok(n)], key=lambda n: (pdate(n["start"]) > today, n["start"]))[:6]
    if not items:
        print("Δεν υπάρχουν ενεργές ειδήσεις για βίντεο."); return None
    W, H = 1080, 1920
    work = os.path.join(OUT, "_short"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    scenes = [("intro", intro_html(W, H, today, len(items)), 3.2, "CQ DX")]
    for i, n in enumerate(items, 1):
        scenes.append((f"s{i}", card_html(n, W, H, today, i, len(items)), 4.8, n.get("call") or ""))
    scenes.append(("outro", outro_html(W, H), 3.8, "73 SK"))
    render_pngs([(h_, os.path.join(work, f"{k}.png"), W, H) for k, h_, _, _ in scenes])
    # video
    lst = []
    for k, _, dur, _ in scenes:
        mp4 = os.path.join(work, f"{k}.mp4"); still_clip(os.path.join(work, f"{k}.png"), dur, mp4); lst.append(mp4)
    open(os.path.join(work, "list.txt"), "w").write("".join(f"file '{p}'\n" for p in lst))
    silent = os.path.join(work, "video.mp4")
    ff(["-f", "concat", "-safe", "0", "-i", os.path.join(work, "list.txt"), "-c", "copy", silent])
    # audio: CW στην αρχή κάθε σκηνής
    total = sum(s[2] for s in scenes)
    audio = np.zeros(int(SR * (total + 0.5))); t = 0.0
    for _, _, dur, txt in scenes:
        clip = cw(re.sub(r"[^A-Z0-9/ ]", "", txt.upper()), wpm=26)[: int(SR * (dur - 0.5))]
        a = int(SR * (t + 0.4)); audio[a:a + len(clip)] += clip; t += dur
    wav = os.path.join(work, "cw.wav")
    with wave.open(wav, "w") as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR)
        wv.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    out = os.path.join(OUT, f"short-{today.isoformat()}.mp4"); tmp = out[:-4] + ".tmp.mp4"
    ff(["-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", tmp])
    os.replace(tmp, out)
    calls = ", ".join(n.get("call") for n in items)
    txt = (f"TITLE: This Week in DX: {calls} #shorts\n\n"
           f"DESCRIPTION:\nDXpeditions and DX stations on the air this week ({fdate(today)} – {fdate(horizon)} {horizon.year}):\n" +
           "".join(f"• {n.get('call')} – {n.get('entity_en') or ''} ({dates_text(n)}): {SITE_SHORT}/dx/{n.get('slug') or ''}/\n" for n in items) +
           f"\nSources are listed on each page. 73 de {CALL}\n\n#hamradio #amateurradio #DX #DXpedition #shorts\n")
    open(out[:-4] + ".txt", "w", encoding="utf-8").write(txt)
    print(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("cards", "short"):
        print(__doc__); sys.exit(1)
    cmd_cards(sys.argv[2:]) if sys.argv[1] == "cards" else cmd_short()

# -*- coding: utf-8 -*-
"""섹션 요약 영상 — 대본을 문장 단위로 TTS(교수 목소리)로 읽히고, 그 시각표에 맞춰 덱 슬라이드·교재 크롭·맞춤 프레임 + 영·한 자막을 1080p 영상으로 만든다.
usage (강의 폴더에서):  SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 vid/secvid.py v41_s01 [--dry] [--novideo]
spec(vid/<name>.py): WEEK UNIT DECK OUT LINES[(visual|None, en, ko)] CROP_LABEL{} build_extra(D)
visual: ('deck', n, {'reveal':False, 'hl':k, 'css':'...'}) | ('crop', 'p88_before') | ('extra', k)"""
import asyncio, importlib, json, pathlib, subprocess, sys, hashlib, re, os
W = pathlib.Path(__file__).resolve().parent.parent
os.chdir(W); sys.path.insert(0, str(W)); sys.path.insert(0, str(W / 'vid'))
from narrate import _synth, _silence, spoken, PROF, media_dur
import deck_lib
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

VID = W / 'vid'; CROPS = W / 'crops'; VIDEO = W / 'video'; VIDEO.mkdir(exist_ok=True)
LOCALFONTS = (W / 'localfonts.css').read_text(encoding='utf-8')
GAP, LEAD, SWITCH, TAIL = 0.5, 0.8, 0.35, 1.2          # 문장 뒤 쉼 · 시작 · 화면 바뀔 때 앞 쉼 · 끝
HIDE = "#hud,#bar,#notes{display:none!important} .foot .n{visibility:hidden} .nar,.aud{display:none!important}"
REVEAL = ".st{opacity:1!important;transform:none!important}"
FILL_JS = """(()=>{const s=document.querySelector('.slide.is-on'); if(!s) return;
 s.querySelectorAll('.ix .row[data-a]').forEach(r=>{const al=r.dataset.a.split('|').map(x=>x.trim().toLowerCase().replace(/[’']/g,"'")); const a=r.dataset.a.split('|')[0].trim();
   const inp=r.querySelector('input.gap'); if(inp){inp.value=a; inp.classList.add('ok');}
   r.querySelectorAll('.opt').forEach(o=>{ if(al.indexOf(o.textContent.trim().toLowerCase().replace(/[’']/g,"'"))>-1) o.classList.add('sel','ok'); });});
 s.querySelectorAll('.ix [data-s]').forEach(sp=>{const t=sp.dataset.s.toLowerCase().split(/\\s+/);
   sp.querySelectorAll('.w').forEach(w=>{ if(t.indexOf(w.dataset.b)>-1) w.classList.add('hit'); });});
 s.querySelectorAll('.ix .card-chip[data-bin]').forEach(c=>{const bin=[...s.querySelectorAll('.bin')].find(b=>b.dataset.bin===c.dataset.bin.split('|')[0]);
   if(bin){ bin.querySelector('.pool').appendChild(c); c.classList.add('ok'); }});})()"""
COMPOSE = '''<!doctype html><html><head><meta charset="utf-8"><style>%s
html,body{margin:0;width:1920px;height:1080px;background:#14181C;overflow:hidden;font-family:Inter,"Noto Sans KR",sans-serif}
.stage{position:absolute;left:133px;top:24px;width:1654px;height:930px;border-radius:6px;overflow:hidden;background:#fff;box-shadow:0 24px 70px rgba(0,0,0,.55)}
.stage img{width:100%%;height:100%%;object-fit:contain;display:block}
.stage.crop{display:flex;align-items:center;justify-content:center;background:#FBFAF6}
.stage.crop img{width:auto;height:auto;max-width:94%%;max-height:92%%;box-shadow:0 8px 30px rgba(0,0,0,.18)}
.stage.crop .lab{position:absolute;left:22px;top:16px;font:600 14px/1 "IBM Plex Mono",monospace;letter-spacing:.08em;color:#1E6A45;background:rgba(30,106,69,.10);padding:8px 12px;border-radius:999px}
.cap{position:absolute;left:120px;right:120px;top:962px;height:110px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
.cap .en{font-family:Inter,"Noto Sans KR",sans-serif;font-weight:600;font-size:31px;line-height:1.25;color:#fff;letter-spacing:-.01em}
.cap .ko{font-family:"Noto Sans KR",sans-serif;font-weight:400;font-size:25px;line-height:1.3;color:#B9C3CC;margin-top:7px}
.cap.long .en{font-size:27px;line-height:1.22}.cap.long .ko{font-size:22px;margin-top:5px}
</style></head><body><div class="stage" id="stage"><img id="img" src=""></div>
<div class="cap" id="cap"><div class="en" id="en"></div><div class="ko" id="ko"></div></div>
<script>window.setFrame=(src,en,ko,kind,lab,cls)=>new Promise(res=>{const st=document.getElementById('stage');st.className='stage '+(kind||'');
let l=st.querySelector('.lab');if(l)l.remove();if(kind==='crop'&&lab){l=document.createElement('div');l.className='lab';l.textContent=lab;st.appendChild(l);}
document.getElementById('cap').className='cap '+(cls||'');
document.getElementById('en').textContent=en;document.getElementById('ko').textContent=ko;const im=document.getElementById('img');
const done=()=>document.fonts.ready.then(()=>res(true));if(im.getAttribute('src')===src)return done();im.onload=done;im.onerror=()=>res(false);im.src=src;});</script></body></html>'''

def localize(html):
    html = re.sub(r'<link[^>]*fonts\.g(oogleapis|static)\.com[^>]*>\n?', '', html)
    return html.replace('<style>', '<style>\n' + LOCALFONTS + '\n', 1)

def vis_key(v):
    if v[0] == 'deck':
        o = v[2] if len(v) > 2 else {}
        return (f"deck{v[1]}" + ("_hide" if o.get('reveal') is False else "") + (f"_hl{o['hl']}" if o.get('hl') else "")
                + (f"_c{hashlib.md5(o['css'].encode()).hexdigest()[:6]}" if o.get('css') else ""))
    return f"crop_{v[1]}" if v[0] == 'crop' else f"extra{v[1]}"

def dur_of(p):
    return media_dur(p)

def tts_text(en):
    if re.search(r'[가-힣]', en): return en   # 한국어 대본(발표 덱)은 그대로 읽힌다
    t = spoken(en)
    t = re.sub(r'\b(2\.\d\d)\b', r'audio \1', t)
    return t

async def synth_all(lines):
    sem = asyncio.Semaphore(2)
    async def one(en):
        async with sem: return await _synth(PROF[0], tts_text(en), PROF[1])
    return await asyncio.gather(*(one(en) for _, en, _ in lines))

def build_events(lines, wavs):
    """→ events [(t, visual, en, ko)], audio list [(wav|silence path)], caps [(start,end,en,ko)]"""
    ev, aud, caps = [], [], []; t = 0.0; cur = None
    for i, (v, en, ko) in enumerate(lines):
        if v is not None and v != cur:
            lead = LEAD if i == 0 else SWITCH
            cur = v; ev.append((t, cur, '', '')); aud.append(_silence(lead)); t += lead
        elif i == 0:
            raise SystemExit('첫 줄에는 화면이 있어야 한다')
        d = dur_of(wavs[i]); ev.append((t, cur, en, ko)); caps.append((t, t + d + 0.2, en, ko))
        aud.append(wavs[i]); aud.append(_silence(GAP)); t += d + GAP
    ev.append((t, cur, '', '')); aud.append(_silence(TAIL)); t += TAIL
    return ev, aud, caps, t

async def wait_fonts(pg):
    for _ in range(40):
        if await pg.evaluate("[...document.fonts].filter(f=>f.status==='loading').length") == 0: break
        await pg.wait_for_timeout(100)

def sheet(paths, out, cols=3, w=640, h=360):
    rows = (len(paths) + cols - 1) // cols
    im = Image.new('RGB', (cols * (w + 10) + 10, rows * (h + 28) + 10), 'white'); dr = ImageDraw.Draw(im); font = ImageFont.load_default(size=16)
    for j, (k, p) in enumerate(paths):
        x = 10 + (j % cols) * (w + 10); y = 10 + (j // cols) * (h + 28)
        im.paste(Image.open(p).convert('RGB').resize((w, h), Image.LANCZOS), (x, y + 18)); dr.text((x, y), k, fill='red', font=font)
    im.save(out)

async def main(name, dry=False):
    spec = importlib.import_module(name)
    lines = spec.LINES
    work = VID / name; (work / 'vis').mkdir(parents=True, exist_ok=True); (work / 'frames').mkdir(exist_ok=True)
    if dry:
        n = 0
        for v, en, ko in lines:
            n += len(en.split()); print(('  ' if v is None else f'[{vis_key(v)}] ').ljust(22), en, '|', ko)
        print(f'{len(lines)} lines · {n} words · ≈{n / 2.25 + len(lines) * GAP:.0f}s'); return
    wavs = await synth_all(lines)
    events, aud, caps, total = build_events(lines, wavs)
    print(f'{name}: {len(lines)} lines · {total:.1f}s')
    # 맞춤 프레임
    extra_local = None
    if any(v and v[0] == 'extra' for v, _, _ in lines):
        D = deck_lib.Deck(spec.WEEK, f'영어듣기와 말하기 1 · {spec.WEEK} · {spec.UNIT}', 'extra', spec.WEEK)
        spec.build_extra(D)
        (work / 'extra.html').write_text(D.html(), encoding='utf-8')
        extra_local = work / 'extra_local.html'; extra_local.write_text(localize(D.html()), encoding='utf-8')
    deck_local = W / spec.DECK
    comp = work / 'compose.html'; comp.write_text(COMPOSE % LOCALFONTS, encoding='utf-8')
    visuals = {vis_key(v): v for _, v, _, _ in events}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get('LECTURE_BROWSER') or r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        ctx = await b.new_context(viewport={'width': 1280, 'height': 720}, device_scale_factor=2); pg = await ctx.new_page()
        await pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        vis_path = {}
        for key, v in visuals.items():
            if v[0] == 'crop':
                c = next(CROPS.glob(v[1] + '.*')); vis_path[key] = c; continue
            out = work / 'vis' / f'{key}.png'; vis_path[key] = out
            if out.exists() and out.stat().st_mtime > deck_local.stat().st_mtime: continue   # 2026-10-15: 덱을 다시 조립했으면 옛 화면을 쓰지 않는다
            if v[0] == 'deck':
                o = v[2] if len(v) > 2 else {}
                url = deck_local.resolve().as_uri() + f'#{v[1]}'
                css = HIDE + ('' if o.get('reveal') is False else REVEAL) + (deck_hl(o['hl']) if o.get('hl') else '') + o.get('css', '')
            else:
                url = extra_local.resolve().as_uri() + f'#{v[1]}'; css = HIDE + REVEAL
            await pg.goto(url); await pg.reload(); await pg.wait_for_timeout(450); await pg.add_style_tag(content=css)
            if v[0] == 'deck' and (v[2].get('reveal') is not False if len(v) > 2 else True): await pg.evaluate(FILL_JS)
            await pg.evaluate("document.fonts.ready"); await wait_fonts(pg); await pg.wait_for_timeout(250); await pg.screenshot(path=str(out))
        await ctx.close()
        sheet([(k, p) for k, p in vis_path.items()], work / 'sheet.png')
        ctx2 = await b.new_context(viewport={'width': 1920, 'height': 1080}); pg2 = await ctx2.new_page()
        await pg2.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        await pg2.goto(comp.resolve().as_uri()); await pg2.wait_for_timeout(300)
        frames = []
        for j, (t, v, en, ko) in enumerate(events):
            kind = 'crop' if v[0] == 'crop' else ''; lab = getattr(spec, 'CROP_LABEL', {}).get(v[1], 'TEXTBOOK') if kind else ''
            cls = 'long' if len(en) > 95 or len(ko) > 52 else ''
            assert await pg2.evaluate("([s,e,k,kd,l,c])=>window.setFrame(s,e,k,kd,l,c)", [vis_path[vis_key(v)].resolve().as_uri(), en, ko, kind, lab, cls])
            await wait_fonts(pg2); fp = work / 'frames' / f'e{j:03d}.png'; await pg2.screenshot(path=str(fp)); frames.append((t, fp))
        await b.close()
    lines_txt = [f"file '{fp.name}'\nduration {max(0.05, (frames[j + 1][0] if j + 1 < len(frames) else total) - t):.3f}" for j, (t, fp) in enumerate(frames)]
    lines_txt.append(f"file '{frames[-1][1].name}'"); (work / 'frames' / 'list.txt').write_text('\n'.join(lines_txt) + '\n')
    (work / 'audio.txt').write_text(''.join(f"file '{pathlib.Path(a).resolve()}'\n" for a in aud))
    out = VIDEO / (spec.OUT + '.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(work / 'frames' / 'list.txt'), '-f', 'concat', '-safe', '0', '-i', str(work / 'audio.txt'),
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-tune', 'stillimage', '-profile:v', 'high', '-level', '4.0',
                    '-c:a', 'aac', '-b:a', '96k', '-ar', '44100', '-ac', '1', '-video_track_timescale', '15360', '-shortest', '-movflags', '+faststart', str(out)], check=True)
    def ts(x): h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60; return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    for key, idx in (('en', 2), ('ko', 3)):
        (VIDEO / f'{spec.OUT}.{key}.srt').write_text('\n'.join(f"{i + 1}\n{ts(c[0])} --> {ts(c[1])}\n{c[idx]}\n" for i, c in enumerate(caps)), encoding='utf-8-sig')
    json.dump({'events': [(round(t, 2), vis_key(v), en) for t, v, en, _ in events], 'dur': total}, open(work / 'events.json', 'w'), ensure_ascii=False, indent=1)
    d = dur_of(out); print(f'→ {out.name}  {int(d // 60)}:{int(d % 60):02d}  {out.stat().st_size // 1024} KB  visuals {len(visuals)}  frames {len(frames)}')

def deck_hl(k):
    return (f".slide.is-on .cards .card:not(:nth-child({k})){{opacity:.26}}"
            f".slide.is-on .cards .card:nth-child({k}){{box-shadow:0 0 0 3px var(--brand);transform:translateY(-4px)}}")

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], '--dry' in sys.argv))

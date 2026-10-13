# -*- coding: utf-8 -*-
"""덱 검증: _local 사본(로컬 폰트) → 넘침·노트·푸터·폰트 검사 → contact sheet → 연습 동작 검사 → PDF.
usage: python verify.py DECK.html [--nopdf] [--noshots] [--out DIR]
이어달리기판(lecture-deck-relay): 결과를 DIR/<덱>_verify.json으로도 남기고(슬라이드별 글 포함), 화면은 DIR/shots/에 찍는다."""
import sys, re, asyncio, pathlib, json, subprocess
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

deck = pathlib.Path(sys.argv[1]); NOPDF = '--nopdf' in sys.argv; NOSHOTS = '--noshots' in sys.argv
OUT = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else pathlib.Path('.')
OUT.mkdir(parents=True, exist_ok=True); SHOTS = OUT / 'shots'
stem = deck.stem
RESULT = {'deck': deck.name}
_print = print
def print(*a):   # 화면에도 찍고, 결과 JSON에도 줄로 남긴다
    _print(*a); RESULT.setdefault('log', []).append(' '.join(str(x) for x in a))

# 1. localfonts.css
import os
lf = pathlib.Path(os.environ.get('LECTURE_FONTS') or 'localfonts.css')
if not lf.exists():
    base = pathlib.Path('node_modules/@fontsource').resolve(); parts = []
    for pkg, files in [('noto-sans-kr', ['400.css', '500.css', '700.css', '900.css']),
                       ('inter', ['400.css', '500.css', '600.css', '700.css', '800.css']),
                       ('ibm-plex-mono', ['400.css', '500.css', '400-italic.css', '500-italic.css'])]:
        for f in files:
            css = (base / pkg / f).read_text(encoding='utf-8')
            parts.append(css.replace('url(./files/', f'url(file://{base / pkg}/files/').replace('font-display: swap', 'font-display: block'))
    lf.write_text('\n'.join(parts), encoding='utf-8')

html = deck.read_text(encoding='utf-8')
html_local = re.sub(r'<link[^>]*fonts\.g(oogleapis|static)\.com[^>]*>\n?', '', html)
html_local = html_local.replace('<style>', '<style>\n' + lf.read_text(encoding='utf-8') + '\n', 1)
local = deck.with_name(stem + '_local.html'); local.write_text(html_local, encoding='utf-8')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get('LECTURE_BROWSER') or r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        pg = await b.new_page(viewport={'width': 1280, 'height': 720})
        await pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        await pg.goto(local.resolve().as_uri())
        await pg.wait_for_timeout(600)
        fonts = await pg.evaluate("(()=>[document.fonts.check('16px Inter'),document.fonts.check('16px \"Noto Sans KR\"'),document.fonts.check('12px \"IBM Plex Mono\"')])()")
        r = await pg.evaluate("""(()=>{const ov=[],nn=[],det=[],ixn=[];
          document.querySelectorAll('.slide').forEach((s,i)=>{ s.classList.add('is-on');
            const b=s.querySelector('.body'); if(b){ const bb=b.getBoundingClientRect(); const kids=[...b.children];
              const top=Math.min(...kids.map(k=>k.getBoundingClientRect().top)), bot=Math.max(...kids.map(k=>k.getBoundingClientRect().bottom));
              if(b.scrollHeight>b.clientHeight+1 || bot>bb.bottom+1 || top<bb.top-1){ov.push(i+1);det.push([i+1,Math.round(bot-bb.top),Math.round(bb.height),Math.round(top-bb.top)]);} }
            const n=s.querySelector('.notes-src'); if(!n||!n.textContent.trim()) nn.push(i+1);
            if(!s.querySelector('.foot')) nn.push('nofoot'+(i+1));
            if(s.querySelector('.ix')) ixn.push(i+1); s.classList.remove('is-on');});
          return {ov,nn,det,ixn,total:document.querySelectorAll('.slide').length,ix:document.querySelectorAll('.ix').length};})()""")
        print('fonts', fonts); print('total', r['total'], 'ix', r['ix'], 'ix slides', r['ixn']); print('overflow', r['ov'], r['det']); print('missing notes/foot', r['nn'])
        RESULT.update(fonts=fonts, slides=r['total'], ix=r['ix'], ix_slides=r['ixn'], overflow=r['ov'], overflow_detail=r['det'], missing_notes=r['nn'])
        RESULT['text'] = await pg.evaluate("""(()=>[...document.querySelectorAll('.slide')].map((s,i)=>{
            const c=s.cloneNode(true); const n=c.querySelector('.notes-src'); const notes=n?n.textContent.trim():''; if(n) n.remove();
            c.querySelectorAll('.nar,.foot,audio,video,img,script').forEach(e=>e.remove());
            const t=x=>(x||'').replace(/\\s+/g,' ').trim();
            return {n:i+1, eyebrow:t(c.querySelector('.eyebrow')?.textContent), title:t(c.querySelector('h1,h2')?.textContent),
                    kind:s.classList.contains('s-title')?'title':s.classList.contains('s-divider')?'divider':s.classList.contains('vslide')?'video':s.querySelector('.ix')?'ix':s.querySelector('.page-frame')?'page':'slide',
                    text:t(c.textContent), script:[...s.querySelectorAll('.script')].map(e=>[...e.childNodes].filter(x=>x.nodeType===3).map(x=>x.textContent.trim()).filter(Boolean)).flat(),
                    answers:[...s.querySelectorAll('.ix .row[data-a]')].map(e=>e.dataset.a), notes:notes};}))()""")
        # 점수 총점
        await pg.reload(); await pg.wait_for_timeout(300)
        total_pts = await pg.evaluate("document.getElementById('score')?.textContent")
        await pg.keyboard.press('s'); await pg.wait_for_timeout(100)
        print('score pill', await pg.evaluate("document.getElementById('score').textContent"))
        await pg.keyboard.press('s')

        # 2. 스크린샷 → contact sheet (8장씩 2열)
        if not NOSHOTS:
            shots = []
            for i in range(r['total']):
                await pg.goto(local.resolve().as_uri() + f'#{i+1}'); await pg.reload(); await pg.wait_for_timeout(120)
                # 단계 등장 요소를 모두 연 상태로 찍는다 (정답 상자 확인용)
                await pg.evaluate("document.querySelectorAll('.st').forEach(e=>e.classList.add('on'))"); await pg.wait_for_timeout(350)
                path = str(SHOTS / f'{stem}_{i+1:02d}.png'); SHOTS.mkdir(exist_ok=True)
                await pg.screenshot(path=path); shots.append(path)
            per = 8; W = 640; H = 360
            font = ImageFont.load_default(size=18)
            for k in range(0, len(shots), per):
                grp = shots[k:k+per]; rows = (len(grp) + 1) // 2
                sheet = Image.new('RGB', (W*2 + 30, rows*(H + 30) + 10), 'white'); dr = ImageDraw.Draw(sheet)
                for j, s in enumerate(grp):
                    im = Image.open(s).resize((W, H), Image.LANCZOS); x = 10 + (j % 2)*(W + 10); y = 10 + (j // 2)*(H + 30)
                    sheet.paste(im, (x, y + 20)); dr.text((x, y), f'slide {k+j+1}', fill='red', font=font)
                sheet.save(SHOTS / f'{stem}_sheet{k//per+1}.png')
            print('sheets', (len(shots) + per - 1) // per)

        # 3. 연습 동작 검사 (첫 choose / type / tap / sort 슬라이드 + st + student)
        async def goto(n):
            await pg.goto(local.resolve().as_uri() + f'#{n}'); await pg.reload(); await pg.wait_for_timeout(150)
        kinds = await pg.evaluate("""(()=>{const out={};document.querySelectorAll('.slide').forEach((s,i)=>{const ix=s.querySelector('.ix'); if(!ix) return;
           const k = ix.querySelector('.opt')?'choose':ix.querySelector('input.gap')?'type':ix.querySelector('[data-s]')?'tap':'sort'; if(!(k in out)) out[k]=i+1;}); return out;})()""")
        print('first ix slides', kinds); RESULT['ix_first'] = kinds; RESULT['ix_test'] = {}
        if 'choose' in kinds:
            await goto(kinds['choose'])
            res = await pg.evaluate("""(()=>{const rows=[...document.querySelectorAll('.slide.is-on .ix .row[data-a]')];
               rows.forEach((r,i)=>{const opts=[...r.querySelectorAll('.opt')]; const wants=r.dataset.a.toLowerCase().replace(/[’']/g,"'").split('|'); const nm=o=>o.textContent.trim().toLowerCase().replace(/[’']/g,"'");
                 const ok=opts.find(o=>wants.indexOf(nm(o))>-1); const wrong=opts.find(o=>wants.indexOf(nm(o))<0);
                 (i===0?wrong:ok).click();}); return rows.length;})()""")
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(200)
            RESULT['ix_test']['choose'] = await pg.evaluate("(()=>{const s=document.querySelector('.slide.is-on'); return {ok:s.querySelectorAll('.opt.ok').length,no:s.querySelectorAll('.opt.no').length,fb:s.querySelector('.fb').textContent,st:s.querySelectorAll('.st.on').length,slide:location.hash}})()"); print('choose', RESULT['ix_test']['choose'])
        if 'type' in kinds:
            await goto(kinds['type'])
            inputs = await pg.query_selector_all('.slide.is-on input.gap')
            answers = await pg.evaluate("[...document.querySelectorAll('.slide.is-on .ix .row[data-a]')].map(r=>r.dataset.a)")
            for i, inp in enumerate(inputs):
                await inp.click(); await inp.type('xx' if i == 0 else answers[i].split('|')[0]);
                if i == 0: await pg.keyboard.press('Space')
            await pg.keyboard.press('Enter'); await pg.wait_for_timeout(200)
            RESULT['ix_test']['type'] = await pg.evaluate("(()=>{const s=document.querySelector('.slide.is-on'); return {ok:s.querySelectorAll('input.ok').length,no:s.querySelectorAll('input.no').length,v0:s.querySelector('input.gap').value,fb:s.querySelector('.fb').textContent,slide:location.hash}})()"); print('type', RESULT['ix_test']['type'])
        if 'tap' in kinds:
            await goto(kinds['tap'])
            await pg.evaluate("""(()=>{const s=document.querySelector('.slide.is-on'); const sps=[...s.querySelectorAll('[data-s]')]; let first=true;
               sps.forEach(sp=>{const t=sp.dataset.s.toLowerCase().split(/\\s+/); [...sp.querySelectorAll('.w')].forEach(w=>{ if(t.includes(w.dataset.b)){ if(first){first=false;} else w.click(); } });});
               const ws=[...s.querySelectorAll('.w')].find(w=>!sps.some(sp=>sp.dataset.s.toLowerCase().split(/\\s+/).includes(w.dataset.b))); if(ws) ws.click();})()""")
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(200)
            RESULT['ix_test']['tap'] = await pg.evaluate("(()=>{const s=document.querySelector('.slide.is-on'); return {hit:s.querySelectorAll('.w.hit').length,miss:s.querySelectorAll('.w.miss').length,wrong:s.querySelectorAll('.w.wrong').length,fb:s.querySelector('.fb').textContent,slide:location.hash}})()"); print('tap', RESULT['ix_test']['tap'])
        if 'sort' in kinds:
            await goto(kinds['sort'])
            await pg.evaluate("""(()=>{const s=document.querySelector('.slide.is-on'); const chips=[...s.querySelectorAll('.card-chip')]; const bins=[...s.querySelectorAll('.bin')];
               chips.forEach((c,i)=>{ c.click(); const target=bins.find(b=>b.dataset.bin===c.dataset.bin); const wrong=bins.find(b=>b.dataset.bin!==c.dataset.bin); (i===0?wrong:target).click(); });})()""")
            await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(200)
            RESULT['ix_test']['sort'] = await pg.evaluate("(()=>{const s=document.querySelector('.slide.is-on'); return {ok:s.querySelectorAll('.card-chip.ok').length,no:s.querySelectorAll('.card-chip.no').length,fb:s.querySelector('.fb').textContent,slide:location.hash}})()"); print('sort', RESULT['ix_test']['sort'])
        # st: 첫 정답 슬라이드
        st_slide = await pg.evaluate("(()=>{let n=0; [...document.querySelectorAll('.slide')].some((s,i)=>{ if(s.querySelector('.st')&&!s.querySelector('.ix')){n=i+1;return true;} }); return n;})()")
        await goto(st_slide); await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(100)
        a = await pg.evaluate("[document.querySelectorAll('.slide.is-on .st.on').length, location.hash]")
        await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(100)
        print('st', st_slide, a, await pg.evaluate("location.hash"))
        # student
        await goto(kinds.get('choose', 2)); await pg.keyboard.press('s'); await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(100)
        print('student', await pg.evaluate("(()=>({score:getComputedStyle(document.getElementById('score')).display, fb:document.querySelector('.slide.is-on .fb')?.textContent}))()"))

        # 3b. 오디오: 슬라이드마다 컨트롤(.aud 바 또는 .nar 알약) 정확히 하나 · 본문 바닥이 푸터를 넘지 않는지 · 이어 읽기 · L 키 · 인쇄 숨김
        au = await pg.evaluate("""(()=>{const zero=[],multi=[],foot=[];document.querySelectorAll('.slide').forEach((s,i)=>{ s.classList.add('is-on');
            const n=s.querySelectorAll('.aud').length+s.querySelectorAll('.nar').length+s.querySelectorAll('.vwrap').length; if(n===0 && !s.classList.contains('s-divider') && !s.classList.contains('s-title')) zero.push(i+1); if(n>1) multi.push([i+1,n]);
            const b=s.querySelector('.body'), f=s.querySelector('.foot'); if(b&&f){ const kids=[...b.children]; if(kids.length){ const bot=Math.max(...kids.map(k=>k.getBoundingClientRect().bottom)); if(bot>f.getBoundingClientRect().top) foot.push([i+1,Math.round(bot-f.getBoundingClientRect().top)]); } }
            s.classList.remove('is-on'); });
            const _as=document.getElementById('audio-store'); const st=_as?JSON.parse(_as.textContent):{}; const keys=Object.keys(st);
            const used=new Set([...document.querySelectorAll('[data-aud],[data-nar],[data-nar-ans]')].flatMap(e=>[e.dataset.aud,e.dataset.nar,e.dataset.narAns].filter(Boolean)));
            const missing=[...used].filter(k=>!st[k]); const unused=keys.filter(k=>!used.has(k));
            return {zero,multi,foot,store:keys.length,missing,unused,ans:document.querySelectorAll('[data-nar-ans]').length,aud:document.querySelectorAll('.aud').length,nar:document.querySelectorAll('.nar').length,vid:document.querySelectorAll('.vwrap').length,vsrc:[...document.querySelectorAll('.vwrap video')].map(v=>v.getAttribute('src')||('data-vid:'+v.dataset.vid))};})()""")
        RESULT['audio'] = au
        print('audio controls', {k: au[k] for k in ['aud', 'nar', 'ans', 'store', 'vid']}, '| zero', au['zero'], '| multi', au['multi'], '| missing', au['missing'], '| unused', au['unused'])
        print('video srcs', au['vsrc'])
        print('body past foot', au['foot'])
        # 이어 읽기: data-nar-ans가 있는 첫 슬라이드 — 본문 재생 → 끝으로 감기 → 상자 닫힘이면 대기(pending) → 열면 정답 재생(.ans)
        cont = await pg.evaluate("(()=>{let n=0; [...document.querySelectorAll('.slide')].some((s,i)=>{ if(s.querySelector('[data-nar-ans]')){n=i+1;return true;} }); return n;})()")
        if cont:
            await goto(cont); await pg.click('.slide.is-on .nar'); await pg.wait_for_timeout(400)
            r1 = await pg.evaluate("(()=>{const b=document.querySelector('.slide.is-on .nar'); const a=window.__nar.pool[b.dataset.nar]; return {playing:b.classList.contains('playing'), paused:a?a.paused:null, dur:a?Math.round(a.duration):null}})()")
            await pg.evaluate("(()=>{const b=document.querySelector('.slide.is-on .nar'); const a=window.__nar.pool[b.dataset.nar]; a.currentTime=Math.max(0,a.duration-0.2);})()")
            await pg.wait_for_timeout(900)
            r2 = await pg.evaluate("(()=>{const b=document.querySelector('.slide.is-on .nar'); return {playing:b.classList.contains('playing'), pending:window.__nar.pending()===b, revealed:!!document.querySelector('.slide.is-on .answer.on')}})()")
            await pg.evaluate("document.querySelector('.slide.is-on .answer').classList.add('on')"); await pg.wait_for_timeout(600)
            r3 = await pg.evaluate("(()=>{const b=document.querySelector('.slide.is-on .nar'); const a=window.__nar.pool[b.dataset.narAns]; return {playing:b.classList.contains('playing'), ans:b.classList.contains('ans'), paused:a?a.paused:null, plus:getComputedStyle(b.querySelector('.nar-a')).display}})()")
            await pg.keyboard.press('l'); await pg.wait_for_timeout(200)
            r4 = await pg.evaluate("(()=>{const b=document.querySelector('.slide.is-on .nar'); return {playing:b.classList.contains('playing')}})()")
            for _ in range(3):   # 연습 슬라이드는 첫 → 가 채점에 쓰이므로 해시가 바뀔 때까지
                await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(500)
                if await pg.evaluate("location.hash") != f'#{cont}': break
            r5 = await pg.evaluate(f"(()=>{{const b=document.querySelectorAll('.slide')[{cont-1}].querySelector('.nar'); const a=window.__nar.pool[b.dataset.nar], c=window.__nar.pool[b.dataset.narAns]; return {{playing:b.classList.contains('playing'), aT:a?Math.round(a.currentTime):null, cT:c?Math.round(c.currentTime):null, hash:location.hash}}}})()")
            RESULT['continuation'] = {'slide': cont, 'play': r1, 'ended': r2, 'reveal': r3, 'L': r4, 'leave': r5}
            print('continuation', cont, 'play', r1, '| ended→', r2, '| reveal→', r3, '| L→', r4, '| leave→', r5)
        pr = await pg.evaluate("(()=>{const s=document.querySelector('.slide.is-on')||document.querySelector('.slide'); return null;})()")
        await pg.emulate_media(media='print'); await pg.wait_for_timeout(100)
        RESULT['print_hides'] = await pg.evaluate("(()=>{const n=document.querySelector('.nar'), a=document.querySelector('.aud'); return {nar:n?getComputedStyle(n).display:'-', aud:a?getComputedStyle(a).display:'-'}})()"); print('print hides', RESULT['print_hides'])
        await pg.emulate_media(media='screen')

        # 4. PDF
        if not NOPDF:
            await goto(1)
            await pg.emulate_media(media='print')
            # 인쇄 모드에서는 전 슬라이드가 펼쳐지므로 필요한 폰트가 모두 요청된다 → 로드가 끝날 때까지 기다린다 (font-display:block 상태의 글자는 PDF에서 빠진다)
            await pg.evaluate("document.fonts.ready")
            for _ in range(40):
                st = await pg.evaluate("(()=>{const fs=[...document.fonts]; return {loading:fs.filter(f=>f.status==='loading').length, loaded:fs.filter(f=>f.status==='loaded').length}})()")
                if st['loading'] == 0 and st['loaded'] > 0: break
                await pg.wait_for_timeout(250)
            await pg.wait_for_timeout(500)
            print('fonts before pdf', st)
            await pg.pdf(path=str(OUT / f'{stem}.pdf'), width='1280px', height='720px', print_background=True)
            from pypdf import PdfReader   # Windows 판: poppler 대신 pypdf로 쪽수·서체를 본다
            rd = PdfReader(str(OUT / f'{stem}.pdf')); print('pdf', len(rd.pages), 'pages'); RESULT['pdf_pages'] = len(rd.pages)
            fonts_ = set()
            for pg_ in rd.pages:
                res = pg_.get('/Resources') or {}
                for f_ in (res.get('/Font') or {}).values():
                    fonts_.add(str(f_.get_object().get('/BaseFont')))
            bad = [f_ for f_ in fonts_ if any(x in f_.lower() for x in ('wenquanyi', 'dejavu', 'malgun', 'gulim', 'batang'))]
            print('pdf fonts', sorted(fonts_)[:12], '| system fonts:', bad or 'none'); RESULT['pdf_system_fonts'] = bad
        await b.close()

asyncio.run(main())
(OUT / f'{stem}_verify.json').write_text(json.dumps(RESULT, ensure_ascii=False, indent=1), encoding='utf-8')
_print('verify json', OUT / f'{stem}_verify.json')

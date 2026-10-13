# -*- coding: utf-8 -*-
"""영어듣기와 말하기 1 · 덱 조립 라이브러리 (4주차판 → 6주차: 복수 정답 'a|b' 채점, STUDENT_DEFAULT=1이면 학생 모드로 열림).
직전 주차(3-2) 덱에서 <style>과 <script>를 떼어 그대로 쓰고(3절 보정·v2·ix·v3 포함), 4주차용 부품 CSS만 덧붙인다."""
import re, json, pathlib, base64, os
from narrate import extract, synth_jobs, spoken, IPA, PROF, STORY

# 스타일·스크립트 원본: 환경변수 DECK_SRC > 직전 덱(w3-2.html) > 뼈대 템플릿(deck_template_ELS1.html)
_SRC_FILE = next((f for f in [os.environ.get('DECK_SRC'), 'w3-2.html', 'deck_template_ELS1.html'] if f and pathlib.Path(f).exists()), None)
assert _SRC_FILE, '스타일 원본(w3-2.html 또는 deck_template_ELS1.html)이 없다'
SRC = pathlib.Path(_SRC_FILE).read_text(encoding='utf-8')
STYLE = re.search(r'<style>.*?</style>', SRC, re.S).group(0)
# 스타일 원본이 이미 조립된 덱(낭독·영상 스크립트 포함)이면 그 둘은 빼고 받는다 — 아래 AUDIO_JS·VIDEO_JS가 다시 붙으므로, 두 번 들어가면 낭독 알약이 서로를 끈다 (발표 덱, 2026-10-11)
_BLOCKS = [b for b in re.findall(r'<script>.*?</script>', SRC, re.S)
           if 'narPool' not in b and "w.addEventListener('click', function(e){ e.stopPropagation(); })" not in b]
SCRIPTS = '\n'.join(_BLOCKS)
if '· L 낭독' not in SCRIPTS:
    SCRIPTS = SCRIPTS.replace('· N 노트 · F 전체화면', '· L 낭독 · N 노트 · F 전체화면')
# 6주차: 복수 정답 — data-a="should|has to" 이면 둘 다 정답 (Type은 첫 번째를 정답으로 채운다)
for a, b in [("var want=norm(r.dataset.a),", "var wants=r.dataset.a.split('|').map(norm), want=wants[0],"),
             ("if(norm(inp.value)===want)", "if(wants.indexOf(norm(inp.value))>-1)"),
             ("inp.value=r.dataset.a;", "inp.value=r.dataset.a.split('|')[0];"),
             ("if(norm(o.textContent)===want)", "if(wants.indexOf(norm(o.textContent))>-1)"),
             ("if(sel&&norm(sel.textContent)===want)", "if(sel&&wants.indexOf(norm(sel.textContent))>-1)")]:
    if b in SCRIPTS: continue   # 스타일 원본(6주차 덱)에 이미 적용됨
    assert a in SCRIPTS, a
    SCRIPTS = SCRIPTS.replace(a, b)
if os.environ.get('STUDENT_DEFAULT') == '1':   # 자습판(LMS): 처음부터 학생 모드 — ?teacher 로 열면 교수 모드
    assert "var student=/student/.test(location.search);" in SCRIPTS
    SCRIPTS = SCRIPTS.replace("var student=/student/.test(location.search);", "var student=!/teacher/.test(location.search);")
# 2026-10-13 덱 이어달리기 ④ GPT 덱 검토에서 찾은 결함 — Tap: 신호가 아닌 낱말을 짚으면 1점씩 뺀다(전부 짚으면 100%가 되던 문제, 0점 아래로는 안 내림) · Sort: data-bin="a|b"면 두 칸 모두 정답
for a, b in [("} else if(on) w.classList.add('wrong'); }); });", "} else if(on){ w.classList.add('wrong'); n--; } }); });"),
             ("ix._done=true; ix._n=n;", "if(n<0) n=0; ix._done=true; ix._n=n;"),
             ("if(host&&host.dataset.bin===c.dataset.bin)", "if(host&&c.dataset.bin.split('|').indexOf(host.dataset.bin)>-1)")]:
    if b in SCRIPTS or a not in SCRIPTS: continue
    SCRIPTS = SCRIPTS.replace(a, b)
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+KR:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')
PAGES = json.load(open('pages_b64.json', encoding='utf-8')) if pathlib.Path('pages_b64.json').exists() else {}   # 없으면 지면 자리에 자리표시자
AUDIO = json.load(open('audio_b64.json', encoding='utf-8')) if pathlib.Path('audio_b64.json').exists() else {}

EXTRA_CSS = '''
/* 모노 라벨 안의 한글은 Noto Sans KR로 (PDF에서 시스템 CJK 폰트로 빠지던 문제) */
:root{--font-mono:"IBM Plex Mono","Noto Sans KR","SFMono-Regular",Menlo,Consolas,monospace}
/* ── 4주차 추가 부품 (기획서 index.html에서 빌림): .quote · .timeline · .pill ── */
.quote{border-left:3px solid var(--brand);padding:4px 0 4px 22px;margin:4px 0 16px;max-width:980px}
.quote .q{font-family:var(--font-en);font-size:21px;font-weight:600;line-height:1.45;letter-spacing:-.015em;color:var(--ink)}
.quote .q b{color:var(--brand-deep)}
.quote .a{font-size:13.5px;color:var(--ink-3);margin-top:8px;line-height:1.6}
.quote.warm{border-left-color:var(--accent)} .quote.warm .q b{color:var(--accent-deep)}
.timeline{border-left:2px solid var(--line);padding-left:24px;margin-left:8px}
.tl{position:relative;padding:7px 0}
.tl::before{content:"";position:absolute;left:-31px;top:13px;width:12px;height:12px;border-radius:50%;background:#fff;border:2px solid var(--brand)}
.tl.done::before{background:var(--brand)}
.tl.acc::before{border-color:var(--accent);background:var(--accent)}
.tl .tw2{font-family:var(--font-mono);font-size:10.5px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--brand);margin-bottom:2px}
.tl .tt{font-family:var(--font-en);font-size:15.5px;font-weight:600;letter-spacing:-.01em;color:var(--ink);line-height:1.35}
.tl .td{font-size:12.5px;color:var(--ink-2);margin-top:2px;line-height:1.5}
.pill{display:inline-block;font-family:var(--font-mono);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:var(--r-pill);margin-left:8px;vertical-align:middle;background:var(--brand-soft);color:var(--brand-deep)}
.pill.now{background:var(--accent-soft);color:var(--accent-deep)}
.page-frame .placeholder .big{color:var(--brand)}
.page-frame .placeholder .small{max-width:520px;margin:9px auto 0;line-height:1.6}
.script .rf{background:linear-gradient(transparent 60%,var(--accent-soft) 60%);border-bottom:1px dashed var(--accent);padding:0 1px}
.focus .f-big.sm{font-size:34px;letter-spacing:-.02em}
.ix .q .qk{white-space:nowrap}
.cards.c3 .card .c-en{font-size:15.5px}
/* ── 오디오 바 (TTS 대체 음원) ── */
.aud{display:flex;align-items:center;gap:14px;margin:8px 0 12px;padding:6px 12px 6px 8px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}
.aud audio{height:34px;width:430px;flex:0 0 auto}
.aud .aud-l{font-family:var(--font-mono);font-size:11px;letter-spacing:.03em;color:var(--ink-3);line-height:1.4}
.aud .aud-l em{font-style:normal;color:var(--accent-deep)}
.page-frame.with-aud{height:392px}
.body.tall > .aud{margin:4px 0 8px}   /* 연습·대본 슬라이드의 바는 여백을 줄여 정답 상자가 푸터에 닿지 않게 */
.pair.lead + .aud{margin-top:2px}
@media print{.aud{display:none}}
/* ── 낭독 알약 (Professor voice) — 슬라이드마다 컨트롤 하나: 제목 아래 rule 줄 오른쪽 (정답은 상자를 연 뒤 같은 알약이 이어 읽는다) ── */
.rule-row{position:relative;height:3px;margin-top:16px}
.rule-row .rule{margin-top:0}
.rule-row .nar{position:absolute;right:0;top:50%;transform:translateY(-50%)}
.nar{position:relative;display:inline-flex;align-items:center;gap:7px;height:26px;padding:0 11px 0 6px;border-radius:999px;border:1px solid var(--brand-line);background:var(--brand-soft);color:var(--brand-deep);font-family:var(--font-mono);font-size:11px;letter-spacing:.04em;cursor:pointer;overflow:hidden;white-space:nowrap;transition:background var(--t-base) var(--ease),border-color var(--t-base) var(--ease)}
.nar:hover{background:#fff;border-color:var(--brand)}
.nar .nar-ic{width:16px;height:16px;border-radius:50%;background:var(--brand-deep);position:relative;flex:0 0 auto}
.nar .nar-ic::before{content:"";position:absolute;left:6px;top:4px;border-style:solid;border-width:4px 0 4px 6px;border-color:transparent transparent transparent #fff}
.nar.playing .nar-ic::before{left:5px;top:4.5px;width:2px;height:7px;border:0;background:#fff;box-shadow:4px 0 0 #fff}
.nar .nar-l{font-weight:500}
.nar .nar-d{color:var(--ink-3)}
.nar .nar-bar{position:absolute;left:0;bottom:0;height:2px;width:0;background:var(--brand)}
.nar .nar-a{display:none;color:var(--accent-deep)}
.slide:has(.answer.on) .nar .nar-a,.slide:has(.answer:not(.st)) .nar .nar-a{display:inline}
.nar.playing.ans .nar-bar{background:var(--accent)}
.nar.playing.ans .nar-ic{background:var(--accent-deep)}
.s-divider .d-row{display:flex;align-items:center;gap:10px;margin-top:20px}
.s-divider .d-row .d-ref{margin-top:0}
.rule-row.pg + .body.tall{height:493px}
.rule-row.pg + .body.tall .page-frame{height:434px}   /* 지면 슬라이드에 알약 줄이 더해진 만큼 줄임 */
.nar.light,.s-close .nar{background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.32);color:#fff}
.nar.light:hover,.s-close .nar:hover{background:rgba(255,255,255,.22);border-color:#fff}
.nar.light .nar-ic,.s-close .nar .nar-ic{background:#fff}
.nar.light .nar-ic::before,.s-close .nar .nar-ic::before{border-left-color:var(--brand-deep)}
.nar.light.playing .nar-ic::before,.s-close .nar.playing .nar-ic::before{background:var(--brand-deep);box-shadow:4px 0 0 var(--brand-deep)}
.nar.light .nar-d,.s-close .nar .nar-d{color:rgba(255,255,255,.72)}
.nar.light .nar-bar,.s-close .nar .nar-bar{background:#fff}
.s-title .nar{margin-left:10px;vertical-align:middle}
@media print{.nar{display:none}}
/* ── 영상 슬라이드 (섹션 요약 영상 · 표지·섹션 표지 바로 다음) ── */
.vslide .h-title{font-size:30px;margin-top:8px}
.vslide .body{height:auto;margin-top:12px;display:flex;justify-content:center}
.vwrap{position:relative;width:974px;height:548px;border-radius:10px;overflow:hidden;background:#0F1512;box-shadow:0 18px 50px rgba(0,0,0,.22)}
.vwrap video{width:100%;height:100%;display:block;background:#000;outline:none}
.vwrap .vposter{display:none;width:100%;height:100%;object-fit:cover}
@media print{.vwrap video{display:none}.vwrap .vposter{display:block}}
'''

AUDIO_JS = '''<script>
(function(){
  /* 오디오 바: 클릭이 슬라이드 넘김·정답 열기로 새지 않게 (document 캡처 단계 — deck의 캡처 리스너보다 먼저) */
  document.addEventListener('click', function(e){ if(e.target && e.target.closest && e.target.closest('.aud')){ e.stopImmediatePropagation(); } }, true);
  /* 플레이어에 초점이 있을 때: Space는 재생/정지, 화살표는 초점을 풀고 슬라이드 넘김에 맡긴다 */
  addEventListener('keydown', function(e){ if(e.target && e.target.tagName==='AUDIO'){ if(e.key===' '){ e.stopImmediatePropagation(); return; }
    if(['ArrowRight','ArrowLeft','PageDown','PageUp'].indexOf(e.key)>-1){ e.target.blur(); } } }, true);
  /* 음원 데이터(문서 끝 audio-store)를 한 번만 읽어 각 플레이어의 src로 — 같은 트랙을 여러 슬라이드에서 써도 파일에는 한 번 */
  var store={}; var st=document.getElementById('audio-store'); if(st){ try{ store=JSON.parse(st.textContent); }catch(e){} }
  document.querySelectorAll('audio[data-aud]').forEach(function(a){ var d=store[a.dataset.aud]; if(!d) return;
    fetch(d).then(function(r){return r.blob()}).then(function(b){ a.src=URL.createObjectURL(b); }).catch(function(){ a.src=d; });
    a.addEventListener('play', function(){ narStopAll(); }); });
  /* ── 낭독 알약: 슬라이드마다 하나. 본문(data-nar)을 읽고, 정답 상자(data-nar-ans)는 상자가 열린 뒤 이어 읽는다. L 키 = 알약 클릭 ── */
  var narPool={}, pend=null, fresh={};   /* pend: 본문을 다 읽었지만 정답 상자가 아직 닫혀 있어 기다리는 알약 · fresh[key]: 슬라이드를 떠나 처음으로 되돌린 상태 */
  function narAudio(key){ if(!key) return null; if(narPool[key]) return narPool[key]; var d=store[key]; if(!d) return null; var a=new Audio(d); a.preload='auto'; narPool[key]=a; return a; }
  function revealed(btn){ var s=btn.closest('.slide'); var a=s&&s.querySelector('.answer'); return !!(a && (a.classList.contains('on') || !a.classList.contains('st'))); }
  function setBar(btn,a){ var bar=btn.querySelector('.nar-bar'); if(bar) bar.style.width=(a&&a.duration?a.currentTime/a.duration*100:0)+'%'; }
  function narStopAll(){ Object.keys(narPool).forEach(function(k){ narPool[k].pause(); });
    document.querySelectorAll('.nar.playing').forEach(function(b){ b.classList.remove('playing','ans'); }); }
  function narPlay(btn,key,isAns){ var a=narAudio(key); if(!a) return;
    narStopAll(); document.querySelectorAll('audio').forEach(function(x){ x.pause(); }); pend=null;
    if(a.ended||fresh[key]){ a.currentTime=0; fresh[key]=false; }
    a.ontimeupdate=function(){ setBar(btn,a); };
    a.onended=function(){ btn.classList.remove('playing','ans'); setBar(btn,null);
      if(!isAns && btn.dataset.narAns){ if(revealed(btn)) narPlay(btn,btn.dataset.narAns,true); else pend=btn; } };
    a.play().then(function(){ btn.classList.add('playing'); btn.classList.toggle('ans',!!isAns); }).catch(function(){}); }
  function narToggle(btn){ var mk=btn.dataset.nar, ak=btn.dataset.narAns, a=narAudio(mk), b=narAudio(ak); if(!a) return;
    if(!a.paused){ a.pause(); btn.classList.remove('playing','ans'); return; }
    if(b && !b.paused){ b.pause(); btn.classList.remove('playing','ans'); return; }
    if(b && !fresh[ak] && b.currentTime>0 && !b.ended){ narPlay(btn,ak,true); return; }        /* 정답 낭독 이어서 */
    if(!fresh[mk] && a.currentTime>0 && !a.ended){ narPlay(btn,mk,false); return; }            /* 본문 낭독 이어서 */
    if(b && !fresh[mk] && a.ended && !b.ended && revealed(btn)){ narPlay(btn,ak,true); return; } /* 본문은 끝났고 상자가 열렸다 → 정답 */
    narPlay(btn,mk,false); }                                                      /* 처음부터 */
  function narReset(s){ s.querySelectorAll('.nar').forEach(function(b){ [b.dataset.nar,b.dataset.narAns].forEach(function(k){ var a=k&&narPool[k]; if(a){ a.pause(); a.currentTime=0; fresh[k]=true; } });
    b.classList.remove('playing','ans'); setBar(b,null); if(pend===b) pend=null; }); }
  document.addEventListener('click', function(e){ var b=e.target&&e.target.closest&&e.target.closest('.nar'); if(b){ e.stopImmediatePropagation(); e.preventDefault(); narToggle(b); } }, true);
  addEventListener('keydown', function(e){ if((e.key==='l'||e.key==='L') && !(e.target&&(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'))){
    var s=document.querySelector('.slide.is-on'); var b=s&&s.querySelector('.nar'); if(b){ narToggle(b); e.stopImmediatePropagation(); e.preventDefault(); } } }, true);
  /* 정답 상자가 열리면(.answer.st → .on) 기다리던 알약이 정답을 이어 읽는다 */
  var moA=new MutationObserver(function(ms){ ms.forEach(function(m){ var el=m.target; if(!el.classList.contains('on')) return;
    var s=el.closest('.slide'); if(pend && s && s.contains(pend) && s.classList.contains('is-on')){ var b=pend; pend=null; narPlay(b,b.dataset.narAns,true); } }); });
  document.querySelectorAll('.answer.st').forEach(function(el){ moA.observe(el,{attributes:true,attributeFilter:['class']}); });
  /* 슬라이드를 떠나면 낭독을 멈추고 처음으로 되돌린다 */
  var mo2=new MutationObserver(function(ms){ ms.forEach(function(m){ if(!m.target.classList.contains('is-on')) narReset(m.target); }); });
  document.querySelectorAll('.slide').forEach(function(s){ if(s.querySelector('.nar')) mo2.observe(s,{attributes:true,attributeFilter:['class']}); });
  window.__nar={pool:narPool, pending:function(){return pend;}};   /* 검증 스크립트용 */
  /* 슬라이드를 떠나면 재생 멈춤 */
  var mo=new MutationObserver(function(ms){ ms.forEach(function(m){ var s=m.target; if(!s.classList.contains('is-on')){ s.querySelectorAll('audio').forEach(function(a){ a.pause(); }); } }); });
  document.querySelectorAll('.slide').forEach(function(s){ if(s.querySelector('audio')) mo.observe(s,{attributes:true,attributeFilter:['class']}); });
})();
</script>
'''

VIDEO_JS = """<script>(function(){
  document.querySelectorAll('.vwrap').forEach(function(w){ w.addEventListener('click', function(e){ e.stopPropagation(); }); });   /* 클릭이 슬라이드 넘김으로 새지 않게 (버블 단계 — 캡처에서 막으면 플레이어 컨트롤이 죽는다) */
  addEventListener('keydown', function(e){ if(e.target && e.target.tagName==='VIDEO'){ e.stopImmediatePropagation(); } }, true);  /* 영상에 초점이 있으면 Space·화살표는 영상 것 */
  document.querySelectorAll('video').forEach(function(v){ v.addEventListener('play', function(){ document.querySelectorAll('audio').forEach(function(a){ a.pause(); }); if(window.__nar){ Object.keys(window.__nar.pool).forEach(function(k){ window.__nar.pool[k].pause(); }); document.querySelectorAll('.nar.playing').forEach(function(b){ b.classList.remove('playing','ans'); }); } }); });
  var mo=new MutationObserver(function(ms){ ms.forEach(function(m){ var s=m.target; if(!s.classList.contains('is-on')){ s.querySelectorAll('video').forEach(function(v){ v.pause(); }); } }); });
  document.querySelectorAll('.vslide').forEach(function(s){ mo.observe(s,{attributes:true,attributeFilter:['class']}); });   /* 슬라이드를 떠나면 멈춤 */
})();</script>"""

VLOADER = """<script>
(function(){
  var store = {};
  function decode(k){
    if (store[k]) return store[k];
    var el = document.querySelector('script.vdata[data-vid="' + k + '"]'); if (!el) return null;
    var bin = atob(el.textContent.replace(/\\s+/g, '')), n = bin.length, u8 = new Uint8Array(n);
    for (var i = 0; i < n; i++) u8[i] = bin.charCodeAt(i);
    store[k] = URL.createObjectURL(new Blob([u8], {type: 'video/mp4'}));
    el.textContent = '';   /* base64 원문은 버려 메모리를 돌려준다 */
    return store[k];
  }
  function attach(v){
    if (v.getAttribute('src')) return;
    try { var url = decode(v.getAttribute('data-vid')); if (url) v.src = url; }
    catch (e) { if (window.console) console.error('embedded video', v.getAttribute('data-vid'), e); }
  }
  var vids = Array.prototype.slice.call(document.querySelectorAll('video[data-vid]'));
  function onSlide(s){ if (s.classList.contains('is-on')) s.querySelectorAll('video[data-vid]').forEach(attach); }
  var mo = new MutationObserver(function(ms){ ms.forEach(function(m){ onSlide(m.target); }); });
  vids.forEach(function(v){ var s = v.closest('.slide'); if (s){ onSlide(s); mo.observe(s, {attributes: true, attributeFilter: ['class']}); } });
  var i = 0; function next(){ if (i >= vids.length) return; attach(vids[i++]); setTimeout(next, 200); }
  setTimeout(next, 800);   /* 현재 슬라이드는 즉시, 나머지는 시작 뒤 한 편씩 */
})();
</script>"""

# ────────────────────────────── 부품 HTML ──────────────────────────────
def pair(en, ko, cls=''):
    return f'<div class="pair {cls}"><div class="en">{en}</div><div class="ko">{ko}</div></div>'

def key(en, ko, warm=False):
    return pair(en, ko, 'key warm' if warm else 'key')

def lead(en, ko):
    return pair(en, ko, 'lead')

def pairs_n(*ps):
    return '<div class="pairs-n">' + ''.join(ps) + '</div>'

def tags(items):
    """items: [(text, cls)] cls in '', 'b', 'a', 'k'"""
    return '<div class="tags">' + ''.join(f'<span class="tag {c}">{t}</span>' for t, c in items) + '</div>'

def kick(en, ko):
    return f'<div class="kick">{en} <span class="ko">{ko}</span></div>'

def focus(label, big, en, ko, ftags=None, cls='', small=None, big_cls=''):
    sm = f'<small>{small}</small>' if small else ''
    row = ('<div class="f-rule"></div><div class="f-row">' + ''.join(f'<span class="tag b">{t}</span>' for t in ftags) + '</div>') if ftags else ''
    return (f'<div class="focus {cls}"><div class="f-label">{label}</div><div class="f-big {big_cls}">{big}{sm}</div>'
            f'<div class="f-en">{en}</div><div class="f-ko">{ko}</div>{row}</div>')

def split2(left, right, wide=False):
    return f'<div class="split2 {"wide" if wide else ""}"><div>{left}</div>{right}</div>'

def ticks(items, warn=False):
    """items: [(en, ko)]"""
    return (f'<ul class="ticks {"warn" if warn else ""}">' +
            ''.join(f'<li><div class="en">{e}</div><div class="ko">{k}</div></li>' for e, k in items) + '</ul>')

def stats(items, s4=False):
    """items: [(n, label_html, cls)]"""
    return (f'<div class="stats {"s4" if s4 else ""}">' +
            ''.join(f'<div class="stat {c}"><div class="n">{n}</div><div class="l">{l}</div></div>' for n, l, c in items) + '</div>')

def flow(steps, nf=None):
    """steps: [(fn, ft, fd, on_bool)]"""
    nf = nf or len(steps)
    return (f'<div class="flow" style="--nf:{nf}">' +
            ''.join(f'<div class="fstep {"on" if on else ""}"><div class="fn">{fn}</div><div class="ft">{ft}</div><div class="fd">{fd}</div></div>'
                    for fn, ft, fd, on in steps) + '</div>')

def cards(items, cols=3):
    """items: [(label, en, ko, cls)]"""
    return (f'<div class="cards c{cols}">' +
            ''.join(f'<div class="card {c}"><div class="c-label">{l}</div><div class="c-en">{e}</div><div class="c-ko">{k}</div></div>'
                    for l, e, k, c in items) + '</div>')

def cmp(headers, rows, w0=None):
    th = ''.join(f'<th{" style=width:"+w0 if (i == 0 and w0) else ""}>{h}</th>' for i, h in enumerate(headers))
    body = ''
    for r in rows:
        body += '<tr>' + ''.join(f'<td><div class="t-en">{e}</div><div class="t-ko">{k}</div></td>' for e, k in r) + '</tr>'
    return f'<table class="cmp"><tr>{th}</tr>{body}</table>'

def sched(headers, rows, widths=None, hl=(), acc=()):
    th = ''.join(f'<th{" style=width:"+widths[i] if widths and widths[i] else ""}>{h}</th>' for i, h in enumerate(headers))
    body = ''
    for i, r in enumerate(rows):
        c = 'hl' if i in hl else ('acc' if i in acc else '')
        body += f'<tr class="{c}">' + ''.join(f'<td>{x}</td>' for x in r) + '</tr>'
    return f'<table class="sched"><tr>{th}</tr>{body}</table>'

def script(lines, ko=None):
    """lines: [(spk, text)]"""
    body = ''.join(f'<span class="spk">{s}</span>{t}<br>' for s, t in lines)
    return f'<div class="script">{body}</div>' + (f'<div class="script-ko">{ko}</div>' if ko else '')

def chips(groups):
    """groups: [(heading, [chip,...], plain_bool)]"""
    out = ''
    for h, cs, plain in groups:
        out += (f'<div class="col-h">{h}</div><div class="chips">' +
                ''.join(f'<span class="chip {"plain" if plain else ""}">{c}</span>' for c in cs) + '</div>')
    return out

def rows(items):
    """items: [(title_en, title_ko, en, ko)]"""
    return ('<div class="rows">' +
            ''.join(f'<div class="row"><div class="r-t">{t}<span class="ko">{tk}</span></div><div><div class="r-en">{e}</div><div class="r-ko">{k}</div></div></div>'
                    for t, tk, e, k in items) + '</div>')

def quote(q, a, warm=False):
    return f'<div class="quote {"warm" if warm else ""}"><div class="q">{q}</div><div class="a">{a}</div></div>'

def timeline(items):
    """items: [(tw2, tt, td, cls)]"""
    return ('<div class="timeline">' +
            ''.join(f'<div class="tl {c}"><div class="tw2">{w}</div><div class="tt">{t}</div><div class="td">{d}</div></div>' for w, t, d, c in items) + '</div>')

def q(en, ko):
    return f'<div class="q"><div class="q-en">{en}</div><div class="q-ko">{ko}</div></div>'

def answer(en, ko, label='Answer · 정답과 해설', st=True, style=''):
    return (f'<div class="answer {"st" if st else ""}"{" style="+chr(34)+style+chr(34) if style else ""}><div class="a-label">{label}</div>'
            f'<div class="a-en">{en}</div><div class="a-ko">{ko}</div></div>')

def aud(key_, label):
    """슬라이드 안 오디오 바 (TTS 대체 음원). 음원 데이터는 문서 끝의 audio-store에 한 번만 심고, 로드 때 src를 채운다. 인쇄에서는 숨김."""
    if key_ not in AUDIO:   # audio_b64.json이 없거나 트랙이 없을 때: 자리만 남긴다 (make_audio.py를 먼저 돌리면 채워진다)
        print(f'  [aud] 음원 없음: {key_} → 자리표시자'); return f'<div class="aud"><span class="aud-l">{label} · <em>음원 없음 — make_audio.py 실행 뒤 다시 조립</em></span></div>'
    a = AUDIO[key_]; m, sec = divmod(int(round(a['dur'])), 60)
    return (f'<div class="aud"><audio controls preload="metadata" data-aud="{key_}" aria-label="{label}"></audio>'
            f'<span class="aud-l">{label} · {m}:{sec:02d} · <em>TTS 대체 음원</em></span></div>')

def nar_btn(key_, ans_key=None, light=False):
    """낭독 알약. data-nar = 본문 키, data-nar-ans = 정답 키(정답 상자가 열린 뒤 이어 읽음). {{DUR:key}}는 html()에서 길이로 채운다."""
    cls = 'nar' + (' light' if light else '')
    ans = f' data-nar-ans="{ans_key}"' if ans_key else ''
    plus = f'<span class="nar-a"> +{{{{DUR:{ans_key}}}}}</span>' if ans_key else ''
    return (f'<button class="{cls}" type="button" data-nar="{key_}"{ans} title="이 슬라이드의 영어 낭독 (L){" · 정답은 상자를 연 뒤 이어서" if ans_key else ""}">'
            f'<span class="nar-ic"></span><span class="nar-l">Listen</span><span class="nar-d">{{{{DUR:{key_}}}}}{plus}</span><span class="nar-bar"></span></button>')

def img(key_, alt=''):
    if key_ not in PAGES:
        print(f'  [img] 지면 크롭 없음: {key_} → 자리표시자'); return f'<div class="placeholder"><div class="big">{key_}</div><div class="small">지면 크롭이 없습니다 — crop_pages.py로 pages_b64.json을 만든 뒤 다시 조립</div></div>'
    return f'<img src="{PAGES[key_]}" alt="{alt}">'


# ────────────────────────────── Deck ──────────────────────────────
class Deck:
    def __init__(self, week, foot_left, title, unit_badge):
        self.week, self.FOOT, self.title, self.unit_badge = week, foot_left, title, unit_badge
        self.S = []
        self.jobs = {}      # 낭독 키 → [(text, voice, rate)]
        self.nar_log = []   # (slide no, key, 초안 텍스트) — 검토용
        self.VDATA = []     # 내장 영상 (k, base64) — EMBED 빌드

    # 공통 조각
    def eb(self, sec, pg):
        return f'<div class="eyebrow"><span>{self.week} ▸ {sec}</span><span class="page-ref">{pg}</span></div>'

    def foot(self, notes):
        assert notes and notes.strip(), '노트 없는 슬라이드'
        return f'<div class="foot"><span>{self.FOOT}</span><span class="n"></span></div><div class="notes-src">{notes}</div>'

    def _head(self, sec, pg, t_en, t_ko, ko_title=False, nar_key=None, ans_key=None):
        rule = f'<div class="rule-row"><div class="rule"></div>{nar_btn(nar_key, ans_key)}</div>' if nar_key else '<div class="rule"></div>'
        if ko_title:
            return self.eb(sec, pg) + f'<h1 class="h-title ko">{t_en}</h1>{rule}'
        sub = f'<div class="h-sub">{t_ko}</div>' if t_ko else ''
        return self.eb(sec, pg) + f'<h1 class="h-title">{t_en}</h1>{sub}{rule}'

    # ── 낭독 등록: body에서 영어를 뽑아 jobs에 넣고 (main_key, ans_key, body) 반환 ──
    #   규칙: 슬라이드마다 컨트롤 하나. 듣기 바(.aud)가 있는 슬라이드는 바만(say를 주지 않는 한 낭독 없음).
    #   say / say_ans: None=자동 추출, False=없음, 문자열·목록=대본. 항목 '@file:PATH'는 음원 파일을 그대로 잇고, '@story:TEXT'는 이야기 목소리로 읽는다.
    def _narrate(self, body, say=None, say_ans=None, story=False):
        n = len(self.S) + 1
        main_key, ans_key = f'n{n}', f'n{n}a'
        has_aud = 'class="aud"' in body
        if has_aud and say is None:
            return None, None, body
        auto_main, auto_ans = extract(body, with_script=True)
        def chunks_from(custom, auto, script_voice):
            if custom is False: return []
            if custom is not None:
                lst = custom if isinstance(custom, (list, tuple)) else [x for x in re.split(r'\n+', custom) if x.strip()]
                out = []
                for x in lst:
                    x = x.strip()
                    if x.startswith('@story:'): out.append((x[7:].strip(), STORY[0], STORY[1]))
                    else: out.append((x, PROF[0], PROF[1]))
                return out
            out = []
            for kind, t in auto:
                if IPA.search(t):
                    print(f'  [nar] slide {n}: IPA 포함 → 건너뜀: {t[:70]}'); continue
                v = script_voice if kind == 'script' else PROF
                out.append((t, v[0], v[1]))
            return out
        mc = chunks_from(say, auto_main, STORY if story else PROF)
        ac = chunks_from(say_ans, auto_ans, PROF) if '<div class="answer' in body else []
        mk = ak = None
        if mc:
            self.jobs[main_key] = mc; mk = main_key; self.nar_log.append((n, main_key, [t for t, _, _ in mc]))
            if ac:
                self.jobs[ans_key] = ac; ak = ans_key; self.nar_log.append((n, ans_key, [t for t, _, _ in ac]))
        elif ac:
            print(f'  [nar] slide {n}: 본문 낭독 없음 → 정답 낭독도 생략')
        return mk, ak, body

    # 범용 슬라이드: body는 부품 HTML을 이어 붙인 문자열
    def slide(self, sec, pg, t_en, t_ko, body, notes, tall=False, mid=False, orb='', cls='', ko_title=False, say=None, say_ans=None, story=False):
        bcls = 'body' + (' tall' if tall else '') + (' mid' if mid else '')
        orbh = '' if orb is None else f'<div class="orb-soft {orb}"></div>'
        mk, ak, body = self._narrate(body, say, say_ans, story)
        self.S.append(f'<section class="slide {cls}">{orbh}{self._head(sec, pg, t_en, t_ko, ko_title, mk, ak)}'
                      f'<div class="{bcls}">{body}</div>{self.foot(notes)}</section>')

    # ① 표지
    def title_slide(self, kicker_en, kicker_ko, h1, h1_ko, badge, meta, notes, say=None):
        pill = ''
        if say:
            key_ = f'n{len(self.S) + 1}'
            self.jobs[key_] = [(x.strip(), PROF[0], PROF[1]) for x in (say if isinstance(say, (list, tuple)) else re.split(r'\n+', say)) if x.strip()]
            self.nar_log.append((len(self.S) + 1, key_, [t for t, _, _ in self.jobs[key_]])); pill = nar_btn(key_, light=True)
        self.S.append(f'''<section class="slide s-title">
  <div class="orb" style="width:520px;height:520px;right:-130px;top:-160px"></div>
  <div class="orb" style="width:300px;height:300px;right:120px;bottom:-110px"></div>
  <div class="inner">
    <div class="kicker">{kicker_en}</div>
    <div class="kicker-ko">{kicker_ko}</div>
    <h1>{h1}</h1>
    <div class="h1-ko">{h1_ko}</div>
    <div class="badge">{badge}</div>{pill}
    <div class="meta">{meta}</div>
  </div>{self.foot(notes)}</section>''')

    # ② 목표와 흐름
    def overview(self, pg, goals, flow_, bridge, notes, say=None):
        def col(h, items):
            return (f'<div><div class="col-h">{h}</div>' +
                    ''.join(f'<div class="goal"><div class="num">{i}</div><div class="txt"><div class="g-en">{e}</div><div class="g-ko">{k}</div></div></div>'
                            for i, (e, k) in enumerate(items, 1)) + '</div>')
        body = (f'<div class="cols">{col("Goals · 학습 목표", goals)}{col("Flow · 수업 흐름", flow_)}</div>'
                + key(bridge[0], bridge[1]).replace('class="pair key"', 'class="pair key" style="margin-top:14px"'))
        mk, ak, body = self._narrate(body, say)
        rule = f'<div class="rule-row"><div class="rule"></div>{nar_btn(mk, ak)}</div>' if mk else '<div class="rule"></div>'
        self.S.append(f'<section class="slide"><div class="orb-soft"></div>{self.eb("Overview", pg)}'
                      f'<h1 class="h-title ko">오늘의 목표와 흐름 · Goals &amp; Flow</h1>{rule}'
                      f'<div class="body">{body}</div>{self.foot(notes)}</section>')

    # ③ 섹션 표지 — 낭독 없음이 기본(사용자 결정: 표지까지 읽는 것은 과함). say를 주면 light 알약.
    def divider(self, n, total, en, ko, ref, notes, say=False):
        mk, ak, _ = self._narrate('', say) if say else (None, None, '')
        pill = nar_btn(mk, light=True) if mk else ''
        self.S.append(f'''<section class="slide s-divider">
  <div class="inner"><div class="big">{n}</div><div>
    <div class="of">Section {n} of {total}</div>
    <h2>{en}</h2><div class="d-ko">{ko}</div><div class="d-row"><div class="d-ref">{ref}</div>{pill}</div>
  </div></div>{self.foot(notes)}</section>''')

    # ④ 교재 지면 (영역 크롭 1–2개, 또는 자리표시자). audio=바(컨트롤 하나) / say=지시문 낭독 알약(바가 없을 때만)
    def page(self, sec, pg, title_ko, keys, cap, notes, placeholder=None, audio=None, say=None):
        wa = ' with-aud' if audio else ''
        if placeholder:
            big, small = placeholder
            frame = f'<div class="page-frame{wa}"><div class="placeholder"><div class="big">{big}</div><div class="small">{small}</div></div></div>'
        else:
            keys = [keys] if isinstance(keys, str) else keys
            frame = f'<div class="page-frame {"split" if len(keys) > 1 else ""}{wa}">' + ''.join(img(k) for k in keys) + '</div>'
        bar = aud(*audio) if audio else ''
        rule = ''
        if say and not audio:
            mk, ak, _ = self._narrate('', say)
            if mk: rule = f'<div class="rule-row pg"><div class="rule"></div>{nar_btn(mk)}</div>'
        self.S.append(f'<section class="slide">{self.eb(sec, pg)}<h1 class="h-title ko">{title_ko}</h1>{rule}'
                      f'<div class="body tall">{frame}<div class="page-cap">{cap}</div>{bar}</div>{self.foot(notes)}</section>')

    # ⑪ 영상 슬라이드 — src가 Path면 파일을 base64로 내장(LMS판), 문자열이면 상대 경로(video/…mp4)
    def video(self, sec, pg, t_en, src, poster_b64, notes):
        if isinstance(src, pathlib.Path):
            k = len(self.VDATA) + 1
            self.VDATA.append((k, base64.b64encode(src.read_bytes()).decode('ascii')))
            vtag = f'<video controls preload="metadata" playsinline poster="{poster_b64}" data-vid="{k}"></video>'
        else:
            vtag = f'<video controls preload="metadata" playsinline poster="{poster_b64}" src="{src}"></video>'
        self.S.append(f'<section class="slide vslide">{self.eb(sec, pg)}<h1 class="h-title">{t_en}</h1>'
                      f'<div class="body"><div class="vwrap">{vtag}<img class="vposter" src="{poster_b64}" alt=""></div></div>{self.foot(notes)}</section>')

    # ⑫ 마무리
    def close(self, pg, t_en, t_ko, tag_items, today, hw, nxt, notes, say=None):
        body = tags(tag_items) + cards([('Today · 오늘', today[0], today[1], ''),
                                        ('Homework · 과제', hw[0], hw[1], ''),
                                        ('Next · 다음', nxt[0], nxt[1], '')])
        mk, ak, body = self._narrate(body, say)
        self.S.append(f'<section class="slide s-close"><div class="orb-soft"></div>{self._head("Wrap-up", pg, t_en, t_ko, False, mk, ak)}'
                      f'<div class="body mid">{body}</div>{self.foot(notes)}</section>')

    # ── 인터랙티브 연습 4종 (SKILL.md 5-2절 그대로) ──
    def _ix_wrap(self, sec, pg, t_en, t_ko, hint, inner, a_en, a_ko, notes, label='Answer · 정답과 해설', lead_=None, audio=None, say=None, say_ans=None):
        ans = answer(a_en, a_ko, label) if a_en else ''
        l = (lead(*lead_) if lead_ else '') + (aud(*audio) if audio else '')
        body = f'{l}<div class="ix-top"><span class="ix-hint">{hint}</span></div><div class="ix">{inner}<div class="fb"></div></div>{ans}'
        mk, ak, body = self._narrate(body, say, say_ans)
        self.S.append(f'<section class="slide">{self._head(sec, pg, t_en, t_ko, False, mk, ak)}'
                      f'<div class="body tall">{body}</div>{self.foot(notes)}</section>')

    def ix_choose(self, sec, pg, t_en, t_ko, items, opts, a_en, a_ko, notes, start=1, hint='CHOOSE · 보기를 누른 뒤 → 로 채점', lead_=None, audio=None, say=None, say_ans=None):
        rows_ = ''
        for i, (qq, k, a) in enumerate(items, start):
            o = ''.join(f'<button class="opt">{x}</button>' for x in (opts if isinstance(opts[0], str) else opts[i - start]))
            rows_ += (f'<div class="row" data-a="{a}"><div class="idx">{i}</div><div class="main"><div class="q">{qq}' + (f'<span class="qk">{k}</span>' if k else '') + '</div>'
                      + f'<div class="opts">{o}</div></div></div>')
        self._ix_wrap(sec, pg, t_en, t_ko, hint, rows_, a_en, a_ko, notes, lead_=lead_, audio=audio, say=say, say_ans=say_ans)

    def ix_type(self, sec, pg, t_en, t_ko, items, a_en, a_ko, notes, start=1, hint='TYPE · 빈칸을 모두 쓰고 Enter로 채점', lead_=None, wide=False, audio=None, say=None, say_ans=None):
        rows_ = ''
        for i, (qq, k, a) in enumerate(items, start):
            q2 = qq.replace('___', f'<input class="gap" type="text" autocomplete="off" spellcheck="false"{" style=width:150px" if wide else ""}>')
            rows_ += (f'<div class="row" data-a="{a}"><div class="idx">{i}</div><div class="main"><div class="q">{q2}' + (f'<span class="qk">{k}</span>' if k else '') + '</div></div></div>')
        self._ix_wrap(sec, pg, t_en, t_ko, hint, rows_, a_en, a_ko, notes, lead_=lead_, audio=audio, say=say, say_ans=say_ans)

    def ix_tap(self, sec, pg, t_en, t_ko, lines, a_en, a_ko, notes, hint='TAP · 낱말을 눌러 표시한 뒤 → 로 채점', lead_=None, audio=None, say=None, say_ans=None):
        inner = ''.join(f'<div class="stress-line"><span class="spk">{spk}</span><span data-s="{tg}">{txt}</span></div>' for spk, txt, tg in lines)
        self._ix_wrap(sec, pg, t_en, t_ko, hint, inner, a_en, a_ko, notes, lead_=lead_, audio=audio, say=say, say_ans=say_ans)

    def ix_sort(self, sec, pg, t_en, t_ko, chips_, bins, a_en, a_ko, notes, hint='SORT · 칩을 누르고 칸을 누르면 들어갑니다 · → 로 채점', lead_=None, audio=None, say=None, say_ans=None):
        pool = '<div class="pool">' + ''.join(f'<button class="card-chip" data-bin="{b}">{t}</button>' for t, b in chips_) + '</div>'
        bn = f'<div class="bins" style="--nb:{len(bins)}">' + ''.join(f'<div class="bin" data-bin="{k}"><div class="bin-h">{l}</div><div class="pool"></div></div>' for k, l in bins) + '</div>'
        self._ix_wrap(sec, pg, t_en, t_ko, hint, pool + bn, a_en, a_ko, notes, lead_=lead_, audio=audio, say=say, say_ans=say_ans)

    # ── 출력 ──
    def html(self):
        style = STYLE.replace('</style>', EXTRA_CSS + '\n</style>')
        body = chr(10).join(self.S)
        if self.jobs and os.environ.get('NO_TTS') == '1':   # TTS를 돌릴 수 없는 환경(네트워크 없음): 알약을 빼고 조립한다
            print('  [nar] NO_TTS=1 — 낭독 알약 없이 조립'); body = re.sub(r'<button class="nar[^"]*"[^>]*>.*?</button>', '', body, flags=re.S); self.jobs = {}
        if self.jobs:
            nar = synth_jobs(self.jobs)
            AUDIO.update(nar)
            tot = sum(v['dur'] for v in nar.values()); kb = sum(v['kb'] for v in nar.values())
            print(f'  낭독 {len(nar)}개 · {int(tot//60)}분 {int(tot%60)}초 · {kb//1024}MB')
        def dur(m):
            k = m.group(1)
            if k not in AUDIO: return ''
            d = int(round(AUDIO[k]['dur'])); return f'{d//60}:{d%60:02d}'
        body = re.sub(r'\{\{DUR:([^}]+)\}\}', dur, body)
        used = sorted(set(re.findall(r'data-aud="([^"]+)"', body)) | set(re.findall(r'data-nar="([^"]+)"', body)) | set(re.findall(r'data-nar-ans="([^"]+)"', body)))
        store = ('<script id="audio-store" type="application/json">' + json.dumps({k: AUDIO[k]['src'] for k in used if k in AUDIO}) + '</script>') if used else ''
        vdata = ('\n'.join(f'<script type="text/plain" class="vdata" data-vid="{k}">{b64}</script>' for k, b64 in self.VDATA) + '\n' + VLOADER) if self.VDATA else ''
        return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{self.title}</title>
{FONTS}
{style}
</head>
<body>
<div id="bar"></div>
<div id="stage"><div id="deck">
{body}
</div></div>
{store}
<div id="hud">← → 이동 (▸ 표시는 정답 열기) · L 낭독 · N 노트 · F 전체화면 · P 인쇄(PDF) · S 학생 모드</div>
<div id="notes"><h4>SPEAKER NOTES · 강의 노트</h4><div id="notes-body"></div></div>
{AUDIO_JS}
{SCRIPTS}
{VIDEO_JS}
{vdata}
</body>
</html>'''

    def write(self, path):
        pathlib.Path(path).write_text(self.html(), encoding='utf-8')
        print(path, len(self.S), 'slides', round(pathlib.Path(path).stat().st_size / 1e6, 2), 'MB')
        if self.nar_log:   # 낭독 대본(검토용) — 슬라이드 번호 · 키 · 읽는 문장
            lines = [f'# {self.title} · 낭독 대본 (Professor voice · TTS) — 화면의 영어를 그대로 읽습니다. (a = 정답 상자 — 상자를 연 뒤 같은 알약이 이어 읽음)', '']
            for n, k, chunks in self.nar_log:
                d = AUDIO.get(k, {}).get('dur', 0); lines.append(f'[{n}] {"정답" if k.endswith("a") else "본문"} · {int(d//60)}:{int(d%60):02d}')
                lines += ['  ' + (f'[음원 파일 {c[6:]}]' if c.startswith('@file:') else c) for c in chunks] + ['']
            pathlib.Path(path).with_name(pathlib.Path(path).stem + '_낭독대본.txt').write_text('\n'.join(lines), encoding='utf-8')

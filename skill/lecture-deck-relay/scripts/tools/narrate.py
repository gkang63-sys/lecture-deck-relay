# -*- coding: utf-8 -*-
"""슬라이드 낭독(Professor voice): 슬라이드의 영어 본문을 읽기 순서대로 뽑아 TTS로 읽힌다.
규칙(SKILL.md 2절): 슬라이드의 영어 문장이 곧 대본이다 — 화면의 영어를 그대로 읽고, 한국어는 읽지 않는다.
- 본문(main): .kick .en .q-en .rows .cards ul.ticks table.cmp table.sched .col-h/.chips .stats .flow .timeline .focus .goal .script(오디오 바 없는 슬라이드만)
- 정답(ans): .answer .a-en  → 정답 상자 안의 작은 알약으로 따로 (→ 로 열기 전에는 들리지 않게)
- 건너뜀: .tags .ix .aud .page-frame .page-cap 한국어 요소 전부
"""
import re, html as H, hashlib, subprocess, pathlib, asyncio, os, base64, json
from bs4 import BeautifulSoup, NavigableString

# Windows 판: 인증서 경로 기본값을 두지 않는다(certifi 사용). ffmpeg는 build/bin, 길이는 mutagen으로 잰다.
os.environ['PATH'] = str(pathlib.Path(__file__).resolve().parent / 'bin') + os.pathsep + os.environ['PATH']
def media_dur(path):
    from mutagen import File
    if str(path).lower().endswith('.wav'):
        import wave
        with wave.open(str(path), 'rb') as w: return w.getnframes() / w.getframerate()
    return float(File(str(path)).info.length)
PROXY = os.environ.get('HTTPS_PROXY')
CACHE = pathlib.Path('tts'); CACHE.mkdir(exist_ok=True)
PROF = (os.environ.get('NAR_VOICE', 'en-US-AndrewNeural'), os.environ.get('NAR_RATE', '-8%'))      # 교수 목소리 (발표 덱: ko-KR-InJoonNeural)
STORY = ('en-US-JennyNeural', '-8%')      # 교재 이야기 낭독(95쪽)

HANGUL = re.compile(r'[ㄱ-ㆎ가-힣]+')
IPA = re.compile(r'[ʃʒəɪŋɔæðθʊɛɑɜː]|/[a-zəɪŋɔæðθʊɛɑɜːˈ]+/')

def spoken(t):
    """화면 문자열 → 읽을 문자열. 한글 제거, 기호를 말로."""
    t = H.unescape(t)
    t = re.sub(r'(\d+)분\s*(\d+)초', lambda m: f"{m.group(1)} minute{'s' if m.group(1) != '1' else ''} {m.group(2)} seconds", t)   # 1분 20초 → 1 minute 20 seconds
    t = HANGUL.sub('', t)
    t = re.sub(r'\(\s*[,·\s]*\)', '', t)                       # 한글이 빠져 빈 괄호
    t = t.replace('…', ' ELLIP ')
    reps = [('___', ' blank '), ('&', ' and '), ('→', '. '), ('⇒', '. '), ('·', ', '), ('—', ', '), ('=', ' equals '),
            ('≈', 'about '), ('×', ' by '), ('+', ' plus '), ('Wh-', 'W-H'), ('JNUclass', 'J-N-U class'),
            ('MS Word file (.docx)', 'Microsoft Word file'), ('script (.docx)', 'script as a Word file'), ('(.docx)', ''), ('.docx', 'dot-docx'),
            ('23:59', '11:59 p.m.'), ('12:00', '12 o’clock'), ('¶1', ''), ('¶2', ''), ('#', 'number '), ('-ed', 'ed'), ('-ED', 'ed')]
    for a, b in reps: t = t.replace(a, b)
    t = re.sub(r'\bJNU\b', 'J-N-U', t)
    t = re.sub(r'\bpp\.\s?(\d+)\s?[–-]\s?(\d+)', r'pages \1 to \2', t)
    t = re.sub(r'\bp\.\s?(\d+)', r'page \1', t)
    t = re.sub(r'(\d)\s?–\s?(\d)', r'\1 to \2', t)             # 1–2 minute, 88–90 (en dash만)
    t = t.replace('–', ', ')
    t = re.sub(r'\bMIN\b', 'minutes', t)
    t = re.sub(r'\b0(\d)\b', r'\1', t)                          # 01 → 1
    if not IPA.search(t): t = re.sub(r'\s*/\s*', ' or ', t)      # was / were → was or were (IPA 없는 줄만)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^[\s,.:;!?\-]+', '', t)                        # 앞머리 찌꺼기
    t = re.sub(r'([?!])\s*[.,;:]+', r'\1', t)                     # ?. → ?
    t = re.sub(r'([,.:;])\s*[,.:;]+', r'\1', t)                  # 겹친 구두점
    t = re.sub(r'\s+([,.!?;:])', r'\1', t)
    t = t.replace(' ELLIP ', ' ... ').replace('ELLIP', '...')
    t = re.sub(r'\s+', ' ', t).strip()
    return t

READ_LEAF = ['q-en', 'en', 'c-en', 'g-en', 'r-en', 't-en', 'f-en', 'chip', 'tt', 'ft', 'a-en']
SKIP = ['tags', 'aud', 'nar', 'page-frame', 'page-cap', 'ko', 'ix-top', 'fb', 'f-row', 'f-rule', 'foot', 'notes-src', 'orb-soft', 'ix-hint', 'qk', 'fd', 'td', 'c-ko', 'g-ko', 'r-ko', 't-ko', 'a-ko', 'f-ko', 'script-ko', 'q-ko']

def _txt(el):
    """요소의 텍스트(한글 span 제외)."""
    for k in el.select('.ko, .qk, .fd, .td'):
        k.decompose()
    return el.get_text(' ')

def extract(body_html, with_script=True):
    """→ (main_chunks, ans_chunks). 각 chunk는 읽을 문장 하나(또는 짧은 묶음)."""
    soup = BeautifulSoup(body_html, 'html.parser')
    main, ans = [], []
    def walk(node, in_ans):
        for ch in list(node.children):
            if isinstance(ch, NavigableString): continue
            cls = ch.get('class', []) or []
            if any(c in SKIP for c in cls): continue
            if 'answer' in cls: walk(ch, True); continue
            if 'ix' in cls:
                for row in ch.select('.row'):
                    qq = row.select_one('.q')
                    if not qq: continue
                    for inp in qq.select('input'): inp.replace_with(' blank ')
                    main.append(re.sub(r'^\s*([a-h]|\d{1,2})\s+(?=[A-Z“"])', r'\1. ', _txt(qq)))   # 'a  Chung Ae …' → 'a. Chung Ae …'
                for line in ch.select('.stress-line'):
                    for sp in line.select('.spk'): sp.decompose()
                    main.append(line.get_text(' '))
                chips_ = [c.get_text(' ').strip() for c in ch.select('.pool .card-chip')]
                if chips_: main.append(', '.join(chips_) + '.')
                continue
            if 'a-label' in cls: continue
            if 'script' in cls:
                if with_script:
                    lines = [l for l in re.split(r'<br\s*/?>', str(ch)) if l.strip()]
                    for l in lines:
                        s = BeautifulSoup(l, 'html.parser'); spk = s.select_one('.spk')
                        name = spk.get_text().strip() if spk else ''
                        if spk: spk.decompose()
                        body = s.get_text(' ')
                        if re.search(r'[A-Za-z]', body): (ans if in_ans else main).append('\x00' + (f'{name}: ' if re.search(r'[A-Za-z]', name) else '') + body)
                continue
            if 'kick' in cls or 'col-h' in cls or 'a-label' in cls:
                (ans if in_ans else main).append(_txt(ch)); continue
            if 'r-t' in cls or 'c-label' in cls or 'tw2' in cls or 'fn' in cls or 'f-label' in cls or 'n' in cls or 'f-big' in cls:
                (ans if in_ans else main).append(_txt(ch)); continue
            if ch.name == 'th':
                (ans if in_ans else main).append(_txt(ch)); continue
            if any(c in READ_LEAF for c in cls):
                (ans if in_ans else main).append(_txt(ch)); continue
            if 'stat' in cls and 'stats' not in cls:   # 숫자 타일: '1876, the telephone, Alexander Graham Bell'
                for br in ch.select('br'): br.replace_with(', ')
                n = ch.select_one('.n'); l = ch.select_one('.l')
                (ans if in_ans else main).append((_txt(n) if n else '') + ', ' + (_txt(l) if l else '')); continue
            if 'sched' in cls:   # 표: 행마다 셀을 이어 한 문장
                for tr in ch.select('tr'):
                    cells = [_txt(c) for c in tr.find_all(['th', 'td'])]
                    main.append('. '.join(x.strip() for x in cells if re.search(r'[A-Za-z]', x)))
                continue
            walk(ch, in_ans)
    walk(soup, False)
    def clean(L):
        out = []
        for x in L:
            kind = 'script' if x.startswith('\x00') else 't'
            t = spoken(x.lstrip('\x00'))
            if re.search(r'[A-Za-z]{2}', t): out.append((kind, t))
        return out
    return clean(main), clean(ans)

# ── 합성 ──

def _edge_endpoint():
    """2026-10-13: Microsoft가 읽기 서비스의 접속 주소를 바꿔 옛 주소가 403을 낸다(edge-tts 이슈 #490, 7.2.8 기준 공식 수정 전).
    새 주소(api.msedgeservices.com)로 바꾼다. edge-tts가 고쳐지면 EDGE_TTS_OLD=1로 옛 주소를 쓸 수 있다."""
    if os.environ.get('EDGE_TTS_OLD') == '1':
        return
    import edge_tts.communicate as _c
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN
    _c.WSS_URL = 'wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1?Ocp-Apim-Subscription-Key=' + TRUSTED_CLIENT_TOKEN

async def _synth(voice, text, rate):
    import edge_tts
    _edge_endpoint()
    key = hashlib.md5(f'{voice}|{rate}|{text}'.encode()).hexdigest()[:16]
    mp3 = CACHE / f'{key}.mp3'; wav = CACHE / f'{key}.wav'
    if not wav.exists():
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, voice, rate=rate, proxy=PROXY).save(str(mp3)); break
            except Exception as e:
                if attempt == 2: raise
                await asyncio.sleep(2)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(mp3), '-ar', '24000', '-ac', '1', str(wav)], check=True)
    return wav

def _silence(sec):
    p = CACHE / f'sil_{sec}.wav'
    if not p.exists():
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', str(sec), str(p)], check=True)
    return p

async def _clip(name, chunks, pause, sem):
    """chunks: [(text, voice, rate)]"""
    out = CACHE / f'{name}.mp3'
    if out.exists(): return out
    files = []
    for c, voice, rate in chunks:
        if c.startswith('@file:'):
            src = pathlib.Path(c[6:]); wav = CACHE / (src.stem + '_24k.wav')
            if not wav.exists():
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-ar', '24000', '-ac', '1', str(wav)], check=True)
            files.append(wav); files.append(_silence(pause)); continue
        async with sem:
            files.append(await _synth(voice, c, rate))
        files.append(_silence(pause))
    lst = CACHE / f'{name}.txt'; lst.write_text(''.join(f"file '{f.resolve()}'\n" for f in files))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-ar', '24000', '-ac', '1', '-b:a', '32k', str(out)], check=True)
    return out

def synth_jobs(jobs):
    """jobs: {key: [(text, voice, rate), ...]} → {key: {'src','dur','kb'}}. 캐시: 같은 내용이면 다시 만들지 않는다."""
    async def run():
        sem = asyncio.Semaphore(3); res = {}
        async def one(k, chunks):
            name = 'nar_' + hashlib.md5('|'.join(f'{t}|{v}|{r}' for t, v, r in chunks).encode()).hexdigest()[:14]
            out = await _clip(name, chunks, 0.45, sem)
            dur = media_dur(out)
            res[k] = {'src': 'data:audio/mpeg;base64,' + base64.b64encode(out.read_bytes()).decode(), 'dur': round(dur, 1), 'kb': out.stat().st_size // 1024}
        await asyncio.gather(*(one(k, v) for k, v in jobs.items()))
        return res
    return asyncio.run(run())

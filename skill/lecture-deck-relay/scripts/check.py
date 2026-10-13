# -*- coding: utf-8 -*-
"""단계마다 코드 검사 — 통과하면 작업/검사/<단계>.json에 ok:true가 남고, 차례표가 다음 단계로 넘어간다.

python "<스킬>/scripts/check.py" plan          ① 원문.md · plan.json
python "<스킬>/scripts/check.py" review_plan   ② review_plan_gpt.json
python "<스킬>/scripts/check.py" draft         ③ 출력/초안/ 덱 (verify 실행) + ② 결정 기록
python "<스킬>/scripts/check.py" review_deck   ④ review_deck_gpt.json
python "<스킬>/scripts/check.py" final         ⑤ 출력/최종/ (verify · PDF) + 모든 결정 기록

검사 자체는 표준 라이브러리. draft · final은 덱을 브라우저로 여는 verify.py를 가상환경(LECTURE_PY)으로 부른다.
"""
import datetime, json, os, pathlib, re, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from relay_common import (ROOT, IN, W, O, CHK, LECTURE_PY, LECTURE_BIN, LECTURE_FONTS,
                          load, save, norm, pages_known, page_refs, bad_pages, result)

KINDS = {'title', 'greeting', 'howto', 'overview', 'divider', 'page', 'explain', 'script', 'speak',
         'ix_choose', 'ix_type', 'ix_tap', 'ix_sort', 'video', 'wrapup', 'close'}
R_TYPES = {'원문', '정답', '범위', '일정', '과제', '흐름', '제안'}
D_TYPES = {'원문', '정답', '번역', '해설', '화면', '조작', '흐름', '표현', '제안'}
NEED_EVIDENCE = {'원문', '정답', '범위', '일정', '과제'}
CHOICES = {'받아들임', '유지', '절충'}


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def rel(p):
    return str(pathlib.Path(p).resolve().relative_to(ROOT)).replace('\\', '/')


def stamp(*paths):
    return {rel(p): pathlib.Path(p).stat().st_mtime for p in paths if pathlib.Path(p).exists()}


def finish(name, errors, summary, inputs, **extra):
    ok = not errors
    r = result(name, ok, errors=errors, summary=summary, inputs=inputs, checked_at=now(), **extra)
    print(('통과' if ok else '실패') + f' · {name} · {summary}')
    for e in errors[:30]:
        print('  -', e)
    if len(errors) > 30:
        print(f'  … 외 {len(errors) - 30}건')
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('status.py'))], capture_output=True)   # 진행판 갱신
    return r


# ── 원문.md ──
def source_sections():
    """원문.md → [(머리, 쪽 목록, 본문)]. 머리 형식: ## 지도서 p.21 · AUDIO SCRIPT 1.04"""
    f = W / '원문.md'
    if not f.exists():
        return None
    secs, cur = [], None
    for line in f.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            cur = [line[3:].strip(), page_refs(line), []]; secs.append(cur)
        elif cur is not None:
            cur[2].append(line)
    return [(h, refs, '\n'.join(b)) for h, refs, b in secs]


def source_text():
    secs = source_sections() or []
    return norm(' '.join(b for _, _, b in secs))


# ── ① plan ──
def check_plan(quiet=False):
    errors, warn = [], []
    plan, secs = load(W / 'plan.json'), source_sections()
    if plan is None: errors.append('작업/plan.json이 없다')
    if secs is None: errors.append('작업/원문.md가 없다')
    if errors:
        return finish('plan', errors, '파일 없음', {})
    known = pages_known()
    if not secs: errors.append('원문.md에 「## 교재 p.N · …」 머리가 하나도 없다')
    for h, refs, body in secs:
        if not refs: errors.append(f'원문.md 머리에 쪽 표시가 없다: {h}')
        errors += [f'원문.md: 입력에 없는 쪽 {b} ({h})' for b in bad_pages(refs, known)]
        if not body.strip(): errors.append(f'원문.md: 내용이 빈 절 ({h})')
    src = source_text()
    meta = plan.get('meta', {})
    for k in ['course', 'week', 'title', 'file', 'minutes']:
        if not meta.get(k): errors.append(f'meta.{k}가 없다')
    slides = plan.get('slides', [])
    nq = 0
    for i, s in enumerate(slides, 1):
        tag = f'{i}장'
        if s.get('n') != i: errors.append(f'{tag}: n={s.get("n")} (차례대로 1, 2, 3 …)')
        if s.get('kind') not in KINDS: errors.append(f'{tag}: kind {s.get("kind")!r}는 {sorted(KINDS)} 가운데 하나')
        if not s.get('title'): errors.append(f'{tag}: title이 없다')
        if not s.get('sec'): errors.append(f'{tag}: sec이 없다')
        srcs = s.get('src') or []
        if not srcs: errors.append(f'{tag}: src(출처)가 없다 — 교재 p.N · 지도서 p.N · 운영.md · 새로 씀')
        for x in srcs:
            if not (page_refs(x) or x.startswith('운영.md') or x.startswith('새로 씀') or x.startswith('교안')):
                errors.append(f'{tag}: 출처 형식 {x!r}')
            errors += [f'{tag}: 입력에 없는 쪽 {b}' for b in bad_pages(page_refs(x), known)]
        if s.get('kind', '').startswith('ix_') and not s.get('answer_src'):
            errors.append(f'{tag}: 연습인데 answer_src(정답 출처)가 없다')
        for q in s.get('quote') or []:
            nq += 1
            if norm(q) not in src: errors.append(f'{tag}: 인용이 원문.md에 없다 — {q[:70]!r}')
        if s.get('kind') == 'video':
            v = s.get('video') or {}
            if not v.get('id') or 'answers' not in v: errors.append(f'{tag}: video.id · video.answers(정답 포함 여부)가 필요')
            elif v['answers']:
                later = [t['n'] for t in slides[i:] if t.get('sec') == s.get('sec') and str(t.get('kind', '')).startswith('ix_')]
                if later: errors.append(f'{tag}: 정답이 든 영상 뒤에 같은 섹션의 연습이 있다({later}) — 복습 영상은 섹션 끝에')
    nix = sum(1 for s in slides if str(s.get('kind', '')).startswith('ix_'))
    lo, hi = meta.get('ix_range', [8, 12])
    if not lo <= nix <= hi: errors.append(f'연습 {nix}개 — 범위 {lo}–{hi} (meta.ix_range로 바꿀 수 있다)')
    used = {(a, n) for s in slides for x in s.get('src') or [] for a, n in page_refs(x)}
    for p in sorted(known.get('교재', [])):
        if ('교재', p) not in used: warn.append(f'교재 p.{p}를 출처로 쓴 슬라이드가 없다 (운영.md에서 뺀 범위인지 확인)')
    nv = sum(1 for s in slides if s.get('kind') == 'video')
    summary = f'{len(slides)}장(영상 {nv}) · 연습 {nix}개 · 원문 {len(secs)}절 · 인용 {nq}개 대조'
    return finish('plan', errors, summary, stamp(W / 'plan.json', W / '원문.md'), warnings=warn,
                  counts={'slides': len(slides), 'videos': nv, 'ix': nix, 'quotes': nq})


# ── 검토 공통 ──
def check_items(items, prefix, types, n_max, errors, slide_text=None):
    ids = set(); known = pages_known(); ops = norm((IN / '운영.md').read_text(encoding='utf-8')) if (IN / '운영.md').exists() else ''
    for it in items:
        i = it.get('id', '?')
        if not re.fullmatch(prefix + r'\d+', str(i)): errors.append(f'{i}: id는 {prefix}1, {prefix}2 …')
        if i in ids: errors.append(f'{i}: id가 겹친다')
        ids.add(i)
        if it.get('type') not in types: errors.append(f'{i}: type {it.get("type")!r}는 {sorted(types)} 가운데 하나')
        sl = it.get('slide')
        if sl is not None and not (isinstance(sl, int) and 1 <= sl <= n_max): errors.append(f'{i}: slide {sl}는 1–{n_max}')
        if not it.get('issue'): errors.append(f'{i}: issue(무엇이 문제인가)가 없다')
        ev = it.get('evidence') or {}
        if it.get('type') in NEED_EVIDENCE and not ev:
            errors.append(f'{i}: {it.get("type")} 이의에는 evidence(쪽 + 원문 인용, 또는 슬라이드 글)가 필요')
        if ev.get('page'):
            pg = ev['page']
            if pg.startswith('운영.md'):
                if norm(ev.get('quote', '')) not in ops: errors.append(f'{i}: 운영.md 인용이 운영.md에 없다 — {ev.get("quote", "")[:60]!r}')
            else:
                refs = page_refs(pg)
                if not refs: errors.append(f'{i}: evidence.page 형식 {pg!r} (예: 지도서 p.21)')
                errors += [f'{i}: 입력에 없는 쪽 {b}' for b in bad_pages(refs, known)]
                if not ev.get('quote'): errors.append(f'{i}: evidence.quote(지면의 글 그대로)가 없다')
        if 'slide_text' in ev:
            if slide_text is None: errors.append(f'{i}: slide_text는 덱 검토에서만')
            else:
                n = ev.get('slide') or sl
                if not n or n not in slide_text: errors.append(f'{i}: slide_text를 쓸 때는 slide 번호가 필요')
                elif norm(ev['slide_text']) not in slide_text[n]:
                    errors.append(f'{i}: slide_text가 {n}장 화면에 없다 — {ev["slide_text"][:60]!r}')
    return ids


def decisions_cover(ids, errors):
    dec = load(W / 'decisions.json', [])
    by = {d.get('id'): d for d in dec}
    for i in sorted(ids, key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0)):
        d = by.get(i)
        if not d: errors.append(f'{i}: decisions.json에 결정이 없다'); continue
        if d.get('choice') not in CHOICES: errors.append(f'{i}: choice는 받아들임 · 유지 · 절충')
        if not (d.get('reason') or '').strip(): errors.append(f'{i}: reason(근거)이 없다')
    return dec


# ── ② review_plan ──
def check_review_plan():
    errors = []
    rv, plan = load(W / 'review_plan_gpt.json'), load(W / 'plan.json', {})
    if rv is None:
        return finish('review_plan', ['작업/review_plan_gpt.json이 없다'], '파일 없음', {})
    if rv.get('reviewer') != 'gpt': errors.append('reviewer는 "gpt"')
    if rv.get('verdict') not in {'agree', 'partly', 'disagree'}: errors.append('verdict는 agree · partly · disagree')
    if not rv.get('summary'): errors.append('summary(한국어 2–3문장)가 없다')
    pages = {f'{a} p.{n}' for _, refs, _ in (source_sections() or []) for a, n in refs}
    seen, diffs = set(), 0
    for t in rv.get('transcription') or []:
        for a, n in page_refs(t.get('page', '')):
            if t.get('checked') is True: seen.add(f'{a} p.{n}')
        diffs += len(t.get('diffs') or [])
    miss = sorted(pages - seen)
    if miss: errors.append(f'원문.md의 이 쪽들을 지면 그림과 대조하지 않았다(transcription.checked): {miss}')
    items = rv.get('items') or []
    check_items(items, 'R', R_TYPES, len(plan.get('slides', [])), errors)
    by = {}
    for it in items: by[it.get('type')] = by.get(it.get('type'), 0) + 1
    summary = f'판정 {rv.get("verdict")} · 항목 {len(items)}(' + ' · '.join(f'{k} {v}' for k, v in sorted(by.items())) + f') · 전사 대조 {len(seen)}쪽 · 차이 {diffs}'
    return finish('review_plan', errors, summary, stamp(W / 'review_plan_gpt.json'))


# ── verify 실행 ──
def run_verify(deck, outdir, pdf):
    build = W / 'build'
    env = dict(os.environ, PYTHONIOENCODING='utf-8', LECTURE_FONTS=str(LECTURE_FONTS),
               PATH=str(LECTURE_BIN) + os.pathsep + os.environ.get('PATH', ''))
    args = [str(LECTURE_PY), '-X', 'utf8', 'verify.py', str(deck), '--out', str(outdir)] + ([] if pdf else ['--nopdf'])
    p = subprocess.run(args, cwd=build, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    vj = pathlib.Path(outdir) / f'{pathlib.Path(deck).stem}_verify.json'
    if p.returncode or not vj.exists():
        return None, (p.stdout[-1500:] + p.stderr[-1500:])
    return load(vj), ''


def deck_checks(v, errors, plan_n, label):
    if v['overflow']: errors.append(f'{label}: 넘침 {v["overflow"]}')
    if v['missing_notes']: errors.append(f'{label}: 노트 · 바닥줄 누락 {v["missing_notes"]}')
    if not all(v.get('fonts', [])): errors.append(f'{label}: 서체 로드 {v.get("fonts")}')
    for k, first in (v.get('ix_first') or {}).items():
        t = (v.get('ix_test') or {}).get(k) or {}
        if not t.get('fb') or t.get('slide') != f'#{first}':
            errors.append(f'{label}: 연습 {k}({first}장) 채점 동작 이상 {t}')
    if v['slides'] != plan_n: errors.append(f'{label}: 덱 {v["slides"]}장 · 계획 {plan_n}장')
    src = source_text(); lines = [ln for s in v.get('text', []) for ln in s.get('script', [])]
    bad = [ln for ln in lines if norm(ln) not in src]
    errors += [f'{label}: 대본 줄이 원문.md에 없다 — {ln[:70]!r}' for ln in bad[:10]]
    if len(bad) > 10: errors.append(f'{label}: 대본 줄 불일치 {len(bad)}건')
    return len(lines), len(lines) - len(bad)


def one_html(folder, exclude=('_local', '_LMS')):
    hs = [h for h in pathlib.Path(folder).glob('*.html') if not any(h.stem.endswith(x) for x in exclude)]
    return hs


# ── ③ draft ──
def check_draft():
    errors = []
    if not check_plan()['ok']:
        return finish('draft', ['① 계획 검사가 지금 통과하지 않는다(원문.md · plan.json을 고쳤다면 check.py plan부터)'], '계획 검사 실패', {})
    rv = load(W / 'review_plan_gpt.json', {})
    decisions_cover({it['id'] for it in rv.get('items', []) if it.get('id')}, errors)
    hs = one_html(O / '초안')
    if len(hs) != 1:
        return finish('draft', errors + [f'출력/초안/에 덱 HTML이 하나여야 한다: {[h.name for h in hs]}'], '덱 없음', {})
    deck = hs[0]
    plan = load(W / 'plan.json'); plan_n = sum(1 for s in plan['slides'] if s.get('kind') != 'video')
    out = CHK / 'draft_verify'
    v, log = run_verify(deck, out, pdf=False)
    if v is None:
        return finish('draft', errors + ['verify.py 실행 실패: ' + log], 'verify 실패', {})
    nl, okl = deck_checks(v, errors, plan_n, '초안')
    # GPT가 볼 것: 화면 그림 · 슬라이드별 글
    scr = O / '초안' / '화면'
    if scr.exists(): shutil.rmtree(scr)
    shutil.copytree(out / 'shots', scr)
    save(O / '초안' / 'slides.json', v.get('text', []))
    summary = f'{v["slides"]}장 · 연습 {v["ix"]}개 · 넘침 {len(v["overflow"])} · 노트 누락 {len(v["missing_notes"])} · 대본 줄 {okl}/{nl} 원문 일치 · ② 결정 {len(rv.get("items", []))}건'
    return finish('draft', errors, summary, stamp(deck), deck=rel(deck))


# ── ④ review_deck ──
def check_review_deck():
    errors = []
    rv, slides = load(W / 'review_deck_gpt.json'), load(O / '초안' / 'slides.json', [])
    if rv is None:
        return finish('review_deck', ['작업/review_deck_gpt.json이 없다'], '파일 없음', {})
    if rv.get('reviewer') != 'gpt': errors.append('reviewer는 "gpt"')
    if rv.get('verdict') not in {'agree', 'partly', 'disagree'}: errors.append('verdict는 agree · partly · disagree')
    if not rv.get('summary'): errors.append('summary(한국어 2–3문장)가 없다')
    if rv.get('checked_slides') != len(slides):
        errors.append(f'checked_slides={rv.get("checked_slides")} — 초안 {len(slides)}장을 모두 봐야 한다(출력/초안/화면/)')
    text = {s['n']: norm(s['text'] + ' ' + s.get('notes', '')) for s in slides}
    items = rv.get('items') or []
    check_items(items, 'D', D_TYPES, len(slides), errors, slide_text=text)
    by = {}
    for it in items: by[it.get('type')] = by.get(it.get('type'), 0) + 1
    summary = f'판정 {rv.get("verdict")} · 본 장 {rv.get("checked_slides")}/{len(slides)} · 항목 {len(items)}(' + ' · '.join(f'{k} {v}' for k, v in sorted(by.items())) + ')'
    return finish('review_deck', errors, summary, stamp(W / 'review_deck_gpt.json'))


# ── ⑤ final ──
def check_final():
    errors = []
    if not check_plan()['ok']:
        errors.append('① 계획 검사가 지금 통과하지 않는다')
    ids = set()
    for f, p in [('review_plan_gpt.json', 'R'), ('review_deck_gpt.json', 'D')]:
        ids |= {it['id'] for it in (load(W / f, {}) or {}).get('items', []) if it.get('id')}
    dec = decisions_cover(ids, errors)
    fin = O / '최종'
    hs = one_html(fin)
    lms = list(fin.glob('*_LMS.html'))
    if len(hs) != 1 or len(lms) != 1:
        return finish('final', errors + [f'출력/최종/에 덱 하나와 _LMS.html 하나: {[h.name for h in hs]} · {[h.name for h in lms]}'], '파일 없음', {})
    deck = hs[0]
    if not (fin / f'{deck.stem}_낭독대본.txt').exists(): errors.append('낭독대본.txt가 없다')
    plan = load(W / 'plan.json'); plan_n = len(plan['slides']); nv = sum(1 for s in plan['slides'] if s.get('kind') == 'video')
    out = CHK / 'final_verify'
    v, log = run_verify(deck, out, pdf=True)
    if v is None:
        return finish('final', errors + ['verify.py 실행 실패: ' + log], 'verify 실패', {})
    nl, okl = deck_checks(v, errors, plan_n, '최종')
    au = v.get('audio', {})
    if au.get('zero'): errors.append(f'낭독 · 듣기 컨트롤이 없는 장 {au["zero"]}')
    if au.get('multi'): errors.append(f'컨트롤이 둘 이상인 장 {au["multi"]}')
    if au.get('missing'): errors.append(f'음원 없는 키 {au["missing"]}')
    if au.get('vid') != nv: errors.append(f'영상 {au.get("vid")}편 · 계획 {nv}편')
    c = v.get('continuation') or {}
    if c and not ((c.get('reveal') or {}).get('ans')): errors.append(f'정답 이어 읽기 이상 {c}')
    if v.get('pdf_pages') != v['slides']: errors.append(f'PDF {v.get("pdf_pages")}쪽 · 슬라이드 {v["slides"]}장')
    if v.get('pdf_system_fonts'): errors.append(f'PDF에 시스템 서체 {v["pdf_system_fonts"]}')
    pdf = out / f'{deck.stem}.pdf'
    if pdf.exists(): shutil.copy(pdf, fin / pdf.name)
    lh = lms[0].read_text(encoding='utf-8', errors='replace')
    nvd = lh.count('class="vdata"')
    if nvd != nv: errors.append(f'LMS판 내장 영상 {nvd}편 · 계획 {nv}편')
    if 'fonts.googleapis.com' in lh: errors.append('LMS판이 인터넷 서체를 부른다(서체 내장 필요)')
    ch = {}
    for d in dec: ch[d.get('choice')] = ch.get(d.get('choice'), 0) + 1
    summary = (f'{v["slides"]}장 · 영상 {au.get("vid")} · 낭독 {au.get("nar")} · 듣기 바 {au.get("aud")} · 넘침 {len(v["overflow"])} · '
               f'PDF {v.get("pdf_pages")}쪽 · 대본 줄 {okl}/{nl} · 결정 {len(ids)}(' + ' · '.join(f'{k} {n}' for k, n in sorted(ch.items())) + ')')
    return finish('final', errors, summary, stamp(deck, lms[0], W / 'decisions.json'), deck=rel(deck))


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else ''
    fn = {'plan': check_plan, 'review_plan': check_review_plan, 'draft': check_draft,
          'review_deck': check_review_deck, 'final': check_final}.get(what)
    if not fn:
        sys.exit(__doc__)
    r = fn()
    sys.exit(0 if r['ok'] else 1)

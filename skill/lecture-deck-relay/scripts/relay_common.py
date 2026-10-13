# -*- coding: utf-8 -*-
"""이어달리기 공통 — 경로 · 읽기 · 글 정규화 · 쪽 표시. 표준 라이브러리만."""
import json, os, pathlib, re, sys, unicodedata

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(os.environ.get('RELAY_ROOT') or os.getcwd()).resolve()   # 차시 폴더 = 지금 작업 폴더
SKILL = pathlib.Path(__file__).resolve().parent.parent
IN, W, O = ROOT / '입력', ROOT / '작업', ROOT / '출력'
CHK = W / '검사'
PAGES = W / '쪽' / '목록.json'

# 이 PC의 기본값 (환경변수로 바꾼다)
_BUILD = pathlib.Path(os.environ.get('LECTURE_BUILD', 'lecture-build'))   # 가상환경 · bin/ffmpeg · localfonts.css가 있는 폴더
LECTURE_PY = pathlib.Path(os.environ.get('LECTURE_PY') or _BUILD / '.venv' / 'Scripts' / 'python.exe')
LECTURE_BIN = pathlib.Path(os.environ.get('LECTURE_BIN') or _BUILD / 'bin')
LECTURE_FONTS = pathlib.Path(os.environ.get('LECTURE_FONTS') or _BUILD / 'localfonts.css')

PAGE_RE = re.compile(r'(교재|지도서|교안)\s*p\.?\s*(\d+)')


def load(p, default=None):
    p = pathlib.Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding='utf-8'))


def save(p, obj):
    p = pathlib.Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')


def norm(t):
    """인용 대조용: 유니코드 정규화 · 따옴표 · 대시 · 공백만 맞춘다. 대소문자와 낱말은 그대로 본다."""
    t = unicodedata.normalize('NFC', t or '')
    for a, b in [('’', "'"), ('‘', "'"), ('“', '"'), ('”', '"'), ('—', '-'), ('–', '-'), ('…', '...'), ('\u00a0', ' ')]:
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


def pages_known():
    """prepare.py가 만든 쪽 목록 → {'교재': {10, 11, …}, '지도서': {…}}"""
    m = load(PAGES, {})
    return {k: set(v) for k, v in m.get('pages', {}).items()}


def page_refs(s):
    return [(a, int(b)) for a, b in PAGE_RE.findall(s or '')]


def bad_pages(refs, known):
    return [f'{a} p.{n}' for a, n in refs if a in known and n not in known[a]]


def result(name, ok, **kw):
    """검사 결과를 작업/검사/<name>.json에 남긴다. 통과일 때만 단계 완료 표시가 된다."""
    obj = {'ok': ok, **kw}
    prev = load(CHK / f'{name}.json') or {}
    if ok:   # 처음 통과한 시각은 남긴다 — 뒤 단계가 같은 검사를 다시 돌려도 진행판의 걸린 시간이 바뀌지 않게
        obj['first_ok_at'] = prev.get('first_ok_at') or kw.get('checked_at')
    save(CHK / f'{name}.json', obj)
    return obj


def plan_review_on():
    """② 계획 검토를 할지 — 입력/운영.md에 「계획 검토: 켬」이 있을 때만(2026-10-13 결정: 기본은 덱 검토 한 번).
    새 교재 · 새 단원 · 과제 조건이 바뀐 주처럼 원문 대조가 특히 필요할 때 켠다."""
    f = IN / '운영.md'
    return f.exists() and re.search(r'계획\s*검토\s*[:：]\s*켬', f.read_text(encoding='utf-8')) is not None

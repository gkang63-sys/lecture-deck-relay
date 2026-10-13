# -*- coding: utf-8 -*-
"""차례표 — Claude와 GPT가 같은 차시 폴더에서 이어달리기할 때, 지금 누구 차례인지 알려 준다.

python "<스킬>/scripts/status.py"            전체 진행 (+ 출력/진행판.html)
python "<스킬>/scripts/status.py" gpt        GPT가 지금 할 일 (없으면 누구를 기다리는지)
python "<스킬>/scripts/status.py" claude     Claude가 지금 할 일

판단은 코드 검사 결과 파일(작업/검사/*.json)로만 한다. 검사를 통과했고, 그 뒤로 검사한 파일이 바뀌지 않았어야 「끝」.
내 차례를 처음 알려 줄 때 시작 시각을 작업/시간기록.jsonl에 남긴다(걸린 시간 = 시작 → 검사 통과).
"""
import datetime, html, json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from relay_common import ROOT, W, O, CHK, PAGES, load, plan_review_on

STEPS = [  # (이름, 누가, 검사 결과 파일, 할 일)
    ('준비', '아무나', None, 'python "<스킬>/scripts/prepare.py" — 입력/의 교재 · 지도서 쪽을 작업/쪽/에 뽑는다'),
    ('① 계획', 'claude', 'plan', 'references/계획규칙.md → 작업/원문.md · 작업/plan.json → python "<스킬>/scripts/check.py" plan'),
    ('② 계획 검토', 'gpt', 'review_plan', 'references/계획검토규칙.md → 작업/review_plan_gpt.json → python "<스킬>/scripts/check.py" review_plan'),
    ('③ 조립', 'claude', 'draft', 'references/조립규칙.md → 작업/build/ → 출력/초안/ → python "<스킬>/scripts/check.py" draft'),
    ('④ 덱 검토', 'gpt', 'review_deck', 'references/덱검토규칙.md → 작업/review_deck_gpt.json → python "<스킬>/scripts/check.py" review_deck'),
    ('⑤ 최종', 'claude', 'final', 'references/최종규칙.md → 작업/decisions.json · 낭독 · 영상 · LMS판 → python "<스킬>/scripts/check.py" final'),
    ('⑥ 교수 확정', '교수', None, '출력/최종/의 덱을 넘겨 보고 확정 · 게시'),
]
NAME = {'gpt': 'GPT', 'claude': 'Claude', '아무나': '코드', '교수': '교수'}
LOG = W / '시간기록.jsonl'


def stage_done(chk):
    r = load(CHK / f'{chk}.json')
    if not r or not r.get('ok'):
        return False
    for p, mt in (r.get('inputs') or {}).items():      # 검사 뒤에 파일이 바뀌었으면 다시 검사해야 한다
        f = ROOT / p
        if not f.exists() or abs(f.stat().st_mtime - mt) > 1:
            return False
    return True


done = {'준비': PAGES.exists()}
for name, by, chk, _ in STEPS[1:]:
    done[name] = stage_done(chk) if chk else False
order = [s[0] for s in STEPS]
SKIP = set()
if not plan_review_on() and not done['② 계획 검토']:   # 기본: 계획 검토 없이 덱 검토 한 번
    done['② 계획 검토'] = True; SKIP.add('② 계획 검토')


def ready(name):
    i = order.index(name)
    return all(done[n] for n in order[:i])


def log_start(name, who):
    rows = [json.loads(x) for x in LOG.read_text(encoding='utf-8').splitlines() if x.strip()] if LOG.exists() else []
    if any(r['stage'] == name and r['who'] == who and 'start' in r for r in rows):
        return
    W.mkdir(exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'stage': name, 'who': who, 'start': datetime.datetime.now().isoformat(timespec='seconds')}, ensure_ascii=False) + '\n')


def timeline():
    """단계별 시작(시간기록) · 끝(검사 통과 시각)."""
    starts = {}
    if LOG.exists():
        for x in LOG.read_text(encoding='utf-8').splitlines():
            if x.strip():
                r = json.loads(x); starts.setdefault(r['stage'], r['start'])
    out = {}
    for name, by, chk, _ in STEPS:
        r = load(CHK / f'{chk}.json') if chk else None
        end = (r.get('first_ok_at') or r.get('checked_at')) if r and r.get('ok') else None
        out[name] = (starts.get(name), end)
    return out


def write_board():
    """출력/진행판.html — 교수가 브라우저로 보는 차례표(15초마다 새로 읽음)."""
    tl = timeline(); rows = ''
    for name, by, chk, how in STEPS:
        st = '건너뜀' if name in SKIP else '끝' if done[name] else ('지금 차례' if ready(name) else '기다림')
        r = load(CHK / f'{chk}.json') if chk else None
        summ = html.escape(r.get('summary', '')) if r else ''
        if r and not r.get('ok'):
            summ = '검사 실패 — ' + html.escape('; '.join(r.get('errors', [])[:3]))
        s, e = tl.get(name, (None, None))
        t = ''
        if s and e:
            d = datetime.datetime.fromisoformat(e) - datetime.datetime.fromisoformat(s); m, sec = divmod(int(d.total_seconds()), 60)
            t = f'{s[11:16]} → {e[11:16]} · {m}분 {sec:02d}초'
        elif e:
            t = f'끝 {e[11:16]}'
        rows += (f'<tr class="{ {"끝": "done", "지금 차례": "now"}.get(st, "wait") }"><td>{name}</td><td><span class="who {by}">{NAME[by]}</span></td>'
                 f'<td>{st}</td><td>{summ}</td><td class="t">{t}</td></tr>')
    meta = load(W / 'plan.json', {}).get('meta', {})
    title = html.escape(f"{meta.get('course', '')} {meta.get('week', '')} · {meta.get('title', '')}".strip(' ·')) or html.escape(ROOT.name)
    page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="15"><title>덱 이어달리기 진행판</title><style>
:root{{--ink:#1d2327;--mute:#66707a;--line:#e3e7ea;--brand:#00A56A;--soft:#E6F7F0;--acc:#FF6E40;--accs:#FFF1EC}}
body{{margin:0;padding:28px 16px;font-family:"Noto Sans KR",system-ui,sans-serif;color:var(--ink);background:#fafbfb}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--mute);font-size:13px;margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}}
td{{padding:11px 12px;border-top:1px solid var(--line);vertical-align:top}} tr:first-child td{{border-top:0}}
tr.done td:nth-child(3){{color:var(--brand);font-weight:700}} tr.now{{background:var(--accs)}} tr.now td:nth-child(3){{color:var(--acc);font-weight:700}}
tr.wait{{color:var(--mute)}} .who{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;background:#eef1f3}}
.who.claude{{background:#FBEDE4;color:#9A4A1E}} .who.gpt{{background:var(--soft);color:#00754C}} .who.교수{{background:#ECE8FB;color:#4B3BA0}}
.t{{white-space:nowrap;color:var(--mute);font-size:12.5px}} .foot{{margin-top:14px;color:var(--mute);font-size:12.5px;line-height:1.6}}
@media (max-width:640px){{td{{padding:9px 8px;font-size:13px}} .t{{white-space:normal}}}}
</style></head><body><main><h1>덱 이어달리기 진행판</h1><div class="sub">{title} · 새로 읽은 시각 {datetime.datetime.now():%H:%M:%S}</div>
<table>{rows}</table>
<div class="foot">어느 앱에든 「lecture-deck-relay 스킬로 다음 차례 해 줘」 한 줄. 차례가 아니면 누구를 기다리는지 말하고 멈춘다.<br>
「끝」은 코드 검사를 통과했다는 뜻이다. 걸린 시간 = 그 AI가 차례를 확인한 때부터 검사 통과까지.</div></main></body></html>'''
    O.mkdir(exist_ok=True)
    (O / '진행판.html').write_text(page, encoding='utf-8')


who = sys.argv[1].lower() if len(sys.argv) > 1 else None
if who is None:
    tl = timeline()
    for name, by, _, _ in STEPS:
        mark = '건너뜀' if name in SKIP else '끝' if done[name] else ('할 수 있음' if ready(name) else '기다림')
        s, e = tl.get(name, (None, None))
        print(f'{name:10} {NAME[by]:6} {mark}' + (f'   ({s[11:19] if s else "?"} → {e[11:19]})' if e else ''))
    write_board(); print('진행판:', O / '진행판.html')
    sys.exit(0)

if not done['준비']:
    print(f'먼저 준비: {STEPS[0][3]} (누가 해도 된다)')
    sys.exit(0)
mine = [s for s in STEPS if s[1] == who and not done[s[0]]]
todo = [s for s in mine if ready(s[0])]
if todo:
    name, _, chk, how = todo[0]
    log_start(name, who)
    r = load(CHK / f'{chk}.json')
    again = f'\n지난 검사 실패: {"; ".join(r.get("errors", [])[:5])}' if r and not r.get('ok') else ''
    print(f'지금 {NAME[who]} 차례: {name}\n할 일: {how}{again}')
elif not mine:
    left = [s for s in STEPS if s[2] and not done[s[0]]]   # 2026-10-13 ④ GPT가 찾은 결함: 남은 단계를 보지 않고 교수 확정이라고 했다
    if left:
        print(f'{NAME[who]}가 할 단계는 모두 끝났습니다. 지금은 {left[0][0]}({NAME[left[0][1]]}) 차례입니다.')
    else:
        print(f'{NAME[who]}가 할 단계는 모두 끝났습니다. 다음은 교수 확정: 출력/최종/')
else:
    name = mine[0][0]
    wait = [n for n in order[:order.index(name)] if not done[n]]
    nxt = wait[0]; by = next(s[1] for s in STEPS if s[0] == nxt)
    print(f'지금은 {NAME[who]} 차례가 아닙니다. {nxt}({NAME[by]})이(가) 끝나야 {name}을(를) 할 수 있습니다.')
    if by == 'gpt' and who == 'claude':
        print('Claude가 직접 부를 수 있음: python "<스킬>/scripts/ask_gpt.py" (Codex CLI로 GPT 차례 한 단계)')
write_board()

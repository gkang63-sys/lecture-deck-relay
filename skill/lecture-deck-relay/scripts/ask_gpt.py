# -*- coding: utf-8 -*-
"""GPT 차례를 Claude가 직접 부른다 — 교수가 Codex 앱으로 옮겨 넣지 않아도 된다(2026-10-13 결정).

python "<스킬>/scripts/ask_gpt.py"      지금이 GPT 차례면 Codex CLI(`codex exec`)에 같은 한 줄을 주고 끝날 때까지 기다린다.

GPT는 Codex 앱과 똑같이 이 스킬을 읽고 자기 단계 하나만 한다(차례표 · 검사 · 쓰기 권한 그대로).
걸린 시간과 사용량(tokens used)을 작업/실행기록.json에, 대화 기록을 작업/로그_gpt_<단계>.txt에 남긴다.
Codex CLI는 ChatGPT 앱에 들어 있는 새 판을 먼저 쓴다(npm 옛 판은 새 모델을 못 부른다). 로그인은 교수가 직접.
"""
import datetime, json, os, pathlib, re, shutil, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from relay_common import ROOT, W

PROMPT = ('lecture-deck-relay 스킬로 다음 차례 해 줘. 지금 작업 폴더가 차시 폴더야. '
          '스킬의 SKILL.md와 그 단계의 규칙을 먼저 읽고, 네 단계 하나만 한 뒤 status.py로 다음 차례를 보고하고 멈춰.')
STATUS = pathlib.Path(__file__).with_name('status.py')


def codex_bin():
    app = sorted(pathlib.Path(os.environ.get('LOCALAPPDATA', '')).glob('OpenAI/Codex/bin/*/codex.exe'), key=lambda p: p.stat().st_mtime)
    return str(app[-1]) if app else (shutil.which('codex') or 'codex')


def status(who=''):
    return subprocess.run([sys.executable, '-X', 'utf8', str(STATUS)] + ([who] if who else []), cwd=ROOT,
                          capture_output=True, text=True, encoding='utf-8').stdout.strip()


s = status('gpt')
print(s)
if not s.startswith('지금 GPT 차례'):
    sys.exit(0)
stage = s.split(':', 1)[1].split('\n')[0].strip()
log = W / f'로그_gpt_{re.sub(r"[^0-9A-Za-z가-힣]+", "_", stage).strip("_")}.txt'
cmd = [codex_bin(), 'exec', '-s', 'workspace-write', '--skip-git-repo-check', '-C', str(ROOT), '-']
t0 = time.time(); start = datetime.datetime.now().isoformat(timespec='seconds')
print(f'[{start[11:]}] Codex 부름 · {stage} · 기다리는 중 (로그: {log.name})', flush=True)
with open(log, 'w', encoding='utf-8') as f:
    p = subprocess.run(cmd, cwd=ROOT, input=PROMPT.encode('utf-8'), stdout=f, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONUTF8': '1'})
sec = round(time.time() - t0)
txt = log.read_text(encoding='utf-8', errors='replace')
tok = re.findall(r'tokens used[:\s]*([\d,]+)', txt, re.I)
rec = {'stage': stage, 'who': 'gpt (codex exec)', 'start': start, 'seconds': sec, 'exit': p.returncode,
       'tokens': int(tok[-1].replace(',', '')) if tok else None}
rl = W / '실행기록.json'
rows = json.loads(rl.read_text(encoding='utf-8')) if rl.exists() else []
rows.append(rec); rl.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'끝 · {sec // 60}분 {sec % 60:02d}초 · exit {p.returncode} · tokens {rec["tokens"]}')
print(status())
sys.exit(p.returncode)

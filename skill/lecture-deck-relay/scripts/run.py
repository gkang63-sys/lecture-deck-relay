# -*- coding: utf-8 -*-
"""claude 단계의 실행기 — 작업/build/ 안의 스크립트를 가상환경 파이썬으로 부른다(ffmpeg 경로 · 서체 · UTF-8을 맞춤).

python "<스킬>/scripts/run.py" setup                      공구를 작업/build/로 복사 (처음 한 번, 있는 파일은 두고)
python "<스킬>/scripts/run.py" build.py                   조립
NO_TTS=1 python "<스킬>/scripts/run.py" build.py          낭독 없이 조립 (초안)
python "<스킬>/scripts/run.py" make_audio.py              듣기 트랙(audio_plan.json)
python "<스킬>/scripts/run.py" vid/secvid.py v61_s01      섹션 영상
"""
import os, pathlib, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from relay_common import W, LECTURE_PY, LECTURE_BIN, LECTURE_FONTS

BUILD = W / 'build'
TOOLS = pathlib.Path(__file__).resolve().parent / 'tools'

if len(sys.argv) < 2:
    sys.exit(__doc__)
if sys.argv[1] == 'setup':
    BUILD.mkdir(parents=True, exist_ok=True)
    for f in TOOLS.rglob('*.py'):
        dst = BUILD / f.relative_to(TOOLS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy(f, dst); print('복사', dst.relative_to(W))
    if not (BUILD / 'localfonts.css').exists():
        shutil.copy(LECTURE_FONTS, BUILD / 'localfonts.css'); print('복사 localfonts.css')
    sys.exit(0)

env = dict(os.environ, PYTHONIOENCODING='utf-8', LECTURE_FONTS=str(LECTURE_FONTS),
           PATH=str(LECTURE_BIN) + os.pathsep + os.environ.get('PATH', ''))
sys.exit(subprocess.run([str(LECTURE_PY), '-X', 'utf8', *sys.argv[1:]], cwd=BUILD, env=env).returncode)

# -*- coding: utf-8 -*-
"""준비 — 입력/의 교재 · 지도서 PDF(스캔)에서 쪽 그림을 뽑아 작업/쪽/에 둔다. 두 AI가 같은 그림을 본다.
쪽 번호는 입력/운영.md의 「교재 쪽: 10, 11, 13」 「지도서 쪽: 20, 21」 줄에서 읽는다(PDF 쪽 순서대로).
지도서는 2단 조판이라 4분면(좌상 · 좌하 · 우상 · 우하)도 따로 만든다 — 글씨를 읽기 위해.
pypdf · Pillow가 필요하다. 없으면 LECTURE_PY(가상환경 파이썬)로 다시 돈다."""
import os, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from relay_common import ROOT, IN, W, PAGES, LECTURE_PY, save

try:
    import pypdf
    from PIL import Image
except ImportError:
    if os.environ.get('RELAY_REEXEC'):
        sys.exit('pypdf · Pillow가 없습니다. LECTURE_PY를 확인하세요.')
    env = dict(os.environ, RELAY_REEXEC='1', RELAY_ROOT=str(ROOT), PYTHONIOENCODING='utf-8')
    sys.exit(subprocess.run([str(LECTURE_PY), '-X', 'utf8', __file__, *sys.argv[1:]], env=env).returncode)

ops = (IN / '운영.md').read_text(encoding='utf-8') if (IN / '운영.md').exists() else ''
need = [p for p in ['교재.pdf', '지도서.pdf', '운영.md'] if not (IN / p).exists()]
if need:
    sys.exit('입력/에 없음: ' + ', '.join(need) + ' — 교수에게 넣어 달라고 말하고 멈춘다.')

out = W / '쪽'; out.mkdir(parents=True, exist_ok=True)
pages, files = {}, {}
for book in ['교재', '지도서']:
    m = re.search(rf'{book}\s*쪽\s*[:：]\s*([\d,\s]+)', ops)
    if not m:
        sys.exit(f'입력/운영.md에 「{book} 쪽: …」 줄이 없습니다.')
    nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
    rd = pypdf.PdfReader(str(IN / f'{book}.pdf'))
    if len(rd.pages) != len(nums):
        sys.exit(f'{book}.pdf는 {len(rd.pages)}쪽인데 운영.md에는 {len(nums)}개 쪽 번호가 있습니다.')
    pages[book] = nums
    for pg, n in zip(rd.pages, nums):
        ims = pg.images
        if len(ims) != 1:
            sys.exit(f'{book} p.{n}: 쪽 그림이 {len(ims)}개 — 스캔 PDF(쪽마다 그림 하나)만 다룬다.')
        im = ims[0].image.convert('RGB')
        big = im.resize((1500, round(im.height * 1500 / im.width)), Image.LANCZOS)
        f = out / f'{book}_p{n}.jpg'; big.save(f, quality=88); files[f'{book} p.{n}'] = [f.name]
        if book == '지도서':   # 2단 조판 → 4분면
            w, h = im.size
            for nm, box in [('좌상', (0, 0, w // 2, h // 2)), ('좌하', (0, h // 2, w // 2, h)),
                            ('우상', (w // 2, 0, w, h // 2)), ('우하', (w // 2, h // 2, w, h))]:
                q = im.crop(box); q = q.resize((1400, round(q.height * 1400 / q.width)), Image.LANCZOS)
                fq = out / f'{book}_p{n}_{nm}.jpg'; q.save(fq, quality=88); files[f'{book} p.{n}'].append(fq.name)
save(PAGES, {'pages': pages, 'files': files})
print('쪽 그림:', ', '.join(f'{k} {len(v)}쪽' for k, v in pages.items()), '→', out)

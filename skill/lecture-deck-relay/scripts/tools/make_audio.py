# -*- coding: utf-8 -*-
"""듣기 트랙(TTS 대체 음원) — audio_plan.json → audio_b64.json (+ audio/ 단독 mp3).
대본 글은 이 파일에 두지 않는다. 차시마다 작업/build/audio_plan.json에 지도서 원문 그대로 적는다(원문.md와 같은 문장).
audio_plan.json: {"tracks": {"a104": {"rate": "-6%", "parts": [["en-GB-SoniaNeural", "문장…", 0.9], …]}, …},
                  "export": {"a104": "ELS1_Week6_audio_104_TTS.mp3"}}
원본 출판사 녹음이 아니다 — 덱의 바 라벨에 「TTS 대체 음원」이 붙는다(deck_lib.aud)."""
import asyncio, json, base64, subprocess, pathlib, shutil
from narrate import _synth, _silence, media_dur

plan = json.loads(pathlib.Path('audio_plan.json').read_text(encoding='utf-8'))
CACHE = pathlib.Path('tts'); CACHE.mkdir(exist_ok=True)
OUT = pathlib.Path('audio'); OUT.mkdir(exist_ok=True)


async def build(name, parts, rate):
    files = []
    for voice, text, pause in parts:
        files.append(await _synth(voice, text, rate))
        if pause: files.append(_silence(pause))
    lst = CACHE / f'{name}.txt'
    lst.write_text(''.join(f"file '{f.resolve()}'\n" for f in files))
    out = CACHE / f'{name}.mp3'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst),
                    '-ar', '24000', '-ac', '1', '-b:a', '48k', str(out)], check=True)
    return out, media_dur(out)


async def main():
    res = {}
    for name, t in plan['tracks'].items():
        out, dur = await build(name, t['parts'], t.get('rate', '-6%'))
        res[name] = {'src': 'data:audio/mpeg;base64,' + base64.b64encode(out.read_bytes()).decode(),
                     'dur': round(dur, 1), 'kb': out.stat().st_size // 1024}
        if name in plan.get('export', {}): shutil.copy(out, OUT / plan['export'][name])
        print(f'{name:8s} {dur:6.1f}s {out.stat().st_size // 1024:5d}KB')
    pathlib.Path('audio_b64.json').write_text(json.dumps(res), encoding='utf-8')
    print('tracks', len(res), '· total', sum(v['kb'] for v in res.values()), 'KB')

asyncio.run(main())

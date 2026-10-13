# lecture-deck-relay — Claude가 만들고 GPT가 검토하는 강의 덱

교양영어 강의 덱 제작을 두 AI의 이어달리기로 바꾼 업무 자동화 실습(AI활용 바이브 코딩 실무과정, 2026-10-13).
소개 페이지: https://lecture-deck-relay.vercel.app

- `skill/lecture-deck-relay/` — SKILL.md 하나를 Codex(`~/.codex/skills/`)와 Claude(`~/.claude/skills/`)에 같은 폴더로 넣는다. 차례표 · 진행판 · 단계별 검사 · 조립 공구.
- 실행 환경(claude 단계): 파이썬 가상환경(playwright · edge-tts · pillow · pypdf · mutagen · bs4), Chrome, ffmpeg. 위치는 `LECTURE_BUILD` 또는 `LECTURE_PY` · `LECTURE_BIN` · `LECTURE_FONTS`.
- 교재 지면 · 지도서 원문 · 강의 덱 자체는 넣지 않았다.

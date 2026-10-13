# -*- coding: utf-8 -*-
"""섹션 요약 영상 spec 공용 — 강조 CSS 헬퍼. 덱 부품(english-lecture-deck v3)의 자식 순서를 기준으로 한다."""
DIM = '{opacity:.26}'
RING = '{box-shadow:0 0 0 3px var(--brand);border-radius:10px}'

def _hl(sel, k, ring=False):
    css = f'.slide.is-on {sel}:not(:nth-child({k})){DIM}'
    if ring: css += f'.slide.is-on {sel}:nth-child({k}){RING}'
    return css

def GOAL(k):  return f'.slide.is-on .cols>div:first-child .goal:not(:nth-child({k + 1})){DIM}'   # 목표 k (col-h가 1번째 자식)
def FLOW(k):  return f'.slide.is-on .cols>div:last-child .goal:not(:nth-child({k + 1})){DIM}'    # 흐름 k
def ROW(k):   return _hl('.rows .row', k)                    # rows() 부품
def PAIRN(k): return _hl('.pairs-n .pair', k)                # pairs_n() 부품
def CARD(k):  return (f'.slide.is-on .cards .card:not(:nth-child({k})){DIM}'
                      f'.slide.is-on .cards .card:nth-child({k}){{box-shadow:0 0 0 3px var(--brand);transform:translateY(-4px)}}')
def STEP(k):  return _hl('.flow .fstep', k)                  # flow() 부품
def TL(k):    return _hl('.timeline .tl', k)                 # timeline() 부품
def TICK(k):  return _hl('ul.ticks li', k)                   # ticks() 부품
def STAT(k):  return _hl('.stats .stat', k)                  # stats() 부품
def IXROW(k): return _hl('.ix .row', k)                      # 연습 문항 k
def CELL(r, c): return f'.slide.is-on table.cmp tr:nth-child({r}) td:nth-child({c}){RING}'   # cmp 표: 헤더가 1행 → 첫 자료 행 r=2
def CMPROW(r): return f'.slide.is-on table.cmp tr:not(:first-child):not(:nth-child({r})){DIM}'
def SCHED(r):  return f'.slide.is-on table.sched tr:not(:first-child):not(:nth-child({r})){DIM}'
def CHIPG(k):  # chips() 부품 k번째 묶음(col-h + chips)만 남김 — 묶음이 .body의 앞자리 자식일 때
    a, b = 2 * k - 1, 2 * k
    return f'.slide.is-on .body>.col-h:not(:nth-child({a})),.slide.is-on .body>.chips:not(:nth-child({b})){DIM}'
def CHIP(g, k): return f'{CHIPG(g)}.slide.is-on .body>.chips:nth-child({2 * g}) .chip:not(:nth-child({k})){DIM}'
def SPLIT_LEFT():  return '.slide.is-on .split2>.focus{opacity:.26}'
def SPLIT_RIGHT(): return '.slide.is-on .split2>div:first-child{opacity:.26}'
def QUOTE_ONLY():  return '.slide.is-on .body>*:not(.quote){opacity:.26}'
def KEY_ONLY():    return '.slide.is-on .body>*:not(.pair.key){opacity:.26}'

# ── 맞춤 프레임 (덱 부품으로) ──
def try_frame(D, sec, pg, q_en, q_ko, chips=(), hint=None):
    """'Now you try' 프레임: 질문 인용 + 보기 칩 + 힌트."""
    from deck_lib import kick, quote, tags, key
    body = kick('NOW YOU TRY', '이제 여러분 차례') + quote(q_en, q_ko)
    if chips: body += tags([(c, 'b') for c in chips])
    if hint: body += key(hint[0], hint[1])
    D.slide(sec, pg, 'One more question', '질문 하나 더', body, '·', mid=True, orb=None, say=False)

def open_frame(D, sec, pg, day_en, day_ko, page, en, ko, ftags=()):
    """'See you in class · open page NN' 프레임."""
    from deck_lib import split2, pairs_n, pair, focus
    body = split2(pairs_n(pair(en, ko)), focus(day_en + ' · ' + day_ko, page, 'Open your book to ' + page.replace('p.', 'page ') + '.', '교재 ' + page.replace('p.', '') + '쪽을 펴 두세요.', list(ftags), cls='ink'))
    D.slide(sec, pg, 'See you in class', '수업에서 만나요', body, '·', mid=True, say=False)

def go_frame(D, sec, pg, big, en, ko, f_en, f_ko, ftags=(), title=('Ready? Open your book', '준비됐나요? 교재를 펴세요')):
    """자습 주간용 마무리 프레임: 왼쪽 한 문장 + 오른쪽 검은 패널(쪽수·마감 등)."""
    from deck_lib import split2, pairs_n, pair, focus
    body = split2(pairs_n(pair(en, ko)), focus(sec, big, f_en, f_ko, list(ftags), cls='ink'))
    D.slide(sec, pg, title[0], title[1], body, '·', mid=True, say=False)

# -*- coding: utf-8 -*-
"""index.html から翻訳対象の日本語を集めて、確認用の一覧 i18n/*.md（JA｜EN）を作る。

- 再実行しても、一覧に書き込まれた EN は保持する（JA が変わった行は EN を空に戻す）
- --fill <json>…  下書き JSON（{キー: EN}）の EN を流し込む
- 一覧の形式は i18n_build.py と共通（parse_md / write_md）

使い方:  python -I tools/i18n_extract.py [--fill i18n/draft/ui.json ...]
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'index.html'
OUT = ROOT / 'i18n'
JP = re.compile(r'[぀-ヿ㐀-鿿]')
VOID = {'img', 'br', 'input', 'meta', 'link', 'hr', 'source', 'wbr', 'area', 'col'}
ATTRS = ('aria-label', 'placeholder', 'alt', 'title', 'aria-roledescription')
SKIP_IDS = {'tiles', 'typeName', 'typeCatch', 'typeDesc', 'styleChips', 'typeHint'}   # JS が書き換えるサンプル文言（index.html の I18N_SKIP と同じ）

FILES = {   # 一覧ファイル → 収める節
    'en-ui.md': ['ui', 'html', 'config', 'axes', 'odai'],
    'en-types-zukan.md': ['types', 'zukan'],
    'en-brewers.md': ['beers', 'brewers'],
    'en-story.md': ['story'],
}
TITLES = {
    'ui': 'UI の文言（画面の文字・ボタン・読み上げ・JS のメッセージ）。キー＝日本語そのもの。{n} のような {…} はそのまま残す',
    'html': 'タグ入り・特別な文言（<br> や <b> はそのまま残す）',
    'config': '設定（イベント名・日付・ハッシュタグ）',
    'axes': '4つの軸（結果のタイルとレーダー。短く）',
    'odai': 'ISeeeTL のお題（29問）',
    'types': '16タイプ（名前は2語・18文字以内。スタイル名は一般的な英語表記）',
    'zukan': 'ビアキャラ図鑑（キャラ設定。name は types と共通なので無し）',
    'beers': '協力ブルワリーのフラッグシップ（ブルワリー名・銘柄・スタイル。公式の英語表記があればそれを）',
    'brewers': 'ブルワリー詳細（紹介文・香り・フード・注ぎ方・哲学・地域・小ネタ）',
    'story': '絵本『その一杯は、どう届く？』（t＝見出し、x＝本文。英語版ページの組版にもこの文面を使う）',
}


# ---------------------------------------------------------------- 一覧の読み書き
def parse_md(text):
    """→ {section: [[key, ja, en, where], …]}"""
    out, sec, i = {}, None, 0
    lines = text.split('\n')
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('## '):
            sec = ln[3:].split(' ')[0].strip(); out.setdefault(sec, []); i += 1; continue
        if sec is None:
            i += 1; continue
        if ln.startswith('|') and not ln.startswith('|---') and not ln.startswith('| key') and not ln.startswith('| JA |'):
            cells = [c.strip() for c in ln.strip().strip('|').split('|')]
            if sec == 'ui':
                ja, en, where = (cells + ['', ''])[:3]; key = ja
            else:
                key, ja, en, where = (cells + ['', '', ''])[:4]
            out[sec].append([key, ja, en, where]); i += 1; continue
        if ln.startswith('### '):
            key = ln[4:].strip(); i += 1
            ja, en, where, cur = [], [], '', None
            while i < len(lines) and not lines[i].startswith('### ') and not lines[i].startswith('## '):
                l2 = lines[i]
                if l2.startswith('JA:'): cur = ja; ja.append(l2[3:].strip())
                elif l2.startswith('EN:'): cur = en; en.append(l2[3:].strip())
                elif l2.startswith('場所:'): where = l2[3:].strip()
                elif cur is not None and l2.strip(): cur.append(l2[4:].rstrip() if l2.startswith('    ') else l2.strip())   # 続きの行は4字下げで書かれている
                i += 1
            jat, ent = '\n'.join(ja).strip(), '\n'.join(en).strip()
            if sec == 'ui': key = jat
            out[sec].append([key, jat, ent, where]); continue
        i += 1
    return out


def cell(s):
    return s.replace('|', '｜').replace('\n', ' ')


def write_md(path, sections, header):
    o = [header, '']
    for sec, rows in sections:
        o.append(f'## {sec}')
        o.append(f'<!-- {TITLES.get(sec, "")} -->')
        o.append('')
        table = [r for r in rows if len(r[1]) <= 70 and '\n' not in r[1] and '\n' not in (r[2] or '')]
        blocks = [r for r in rows if r not in table]
        if table:
            o.append('| JA | EN | 場所 |' if sec == 'ui' else '| key | JA | EN | 場所 |')
            o.append('|---|---|---|' if sec == 'ui' else '|---|---|---|---|')
            for key, ja, en, where in table:
                o.append(f'| {cell(ja)} | {cell(en)} | {cell(where)} |' if sec == 'ui' else f'| {key} | {cell(ja)} | {cell(en)} | {cell(where)} |')
            o.append('')
        for key, ja, en, where in blocks:
            o.append(f'### {key if sec != "ui" else "ui"}')
            o.append('JA: ' + ja.replace('\n', '\n    '))
            o.append('EN: ' + (en or '').replace('\n', '\n    '))
            if where: o.append('場所: ' + where)
            o.append('')
    path.write_text('\n'.join(o).rstrip() + '\n', encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- 抽出
class Dom(HTMLParser):
    """body の中のテキストノードと属性（日本語を含むもの）を、実行時の applyLang と同じ範囲で集める"""
    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.src = src
        self.starts = [0]
        for m in re.finditer('\n', src): self.starts.append(m.end())
        self.stack = []        # [tag, skip?, html_key, inner_start]
        self.skip = 0
        self.texts, self.attrs, self.htmls = [], [], []
        self.in_types = False

    def off(self):
        ln, col = self.getpos(); return self.starts[ln - 1] + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class', '')
        is_types = a.get('id') == 's-types'
        if is_types: self.in_types = True
        skip = tag in ('script', 'style') or 'type-card' in cls.split() or a.get('id') in SKIP_IDS or ('types-head' in cls.split() and self.in_types)
        hk = a.get('data-i18n-html')
        if not self.skip and not skip and not hk:
            for k in ATTRS:
                v = a.get(k)
                if v and JP.search(v) and not (k == 'aria-label' and 'scale-btn' in cls.split()):
                    self.attrs.append((v, f'{k} {tag}' + (('#' + a['id']) if a.get('id') else ('.' + cls.split()[0] if cls else ''))))
        if tag in VOID: return
        self.stack.append([tag, skip, hk, self.off() + len(self.get_starttag_text()), is_types])
        if skip or hk: self.skip += 1

    def handle_endtag(self, tag):
        while self.stack:
            t, skip, hk, inner, is_types = self.stack.pop()
            if is_types: self.in_types = False   # 16タイプ一覧の節を抜けたら、ほかの画面の .types-head は対象に戻す
            if skip or hk: self.skip -= 1
            if hk: self.htmls.append((hk, self.src[inner:self.off()].strip()))
            if t == tag: break

    def handle_data(self, d):
        if self.skip: return
        t = d.strip()
        if not t or not JP.search(t): return
        tag, a = (self.stack[-1][0] if self.stack else ''), None
        self.texts.append((t, tag))


def extract(src):
    body = src[src.index('<body>'):src.rindex('<script>')]
    js = src[src.rindex('<script>'):]
    dom = Dom(body); dom.feed(body)
    S = {k: [] for k in TITLES}
    seen = {}
    def ui(ja, where):
        if ja in seen:
            if where not in seen[ja]: seen[ja].append(where)
            return
        seen[ja] = [where]; S['ui'].append([ja, ja, '', where])
    for t, tag in dom.texts: ui(t, tag)
    for v, where in dom.attrs: ui(v, where)
    # JS の t('…') / tf('…')
    for m in re.finditer(r"(?<![\w.$])trf?\('((?:[^'\\]|\\.)*)'", js):
        s = m.group(1).replace("\\'", "'").replace('\\n', '\n')
        if JP.search(s): ui(s, 'JS')
    for ja in seen: pass
    for row in S['ui']: row[3] = '、'.join(seen[row[0]][:3])
    # タグ入り（data-i18n-html と KEYED_JA）
    m = re.search(r'<title>(.*?)</title>', src, re.S)
    S['html'].append(['html.meta.title', m.group(1).strip(), '', '<title>'])
    seen_hk = set()
    for hk, inner in dom.htmls:
        if hk in seen_hk: continue
        seen_hk.add(hk)
        S['html'].append([f'html.{hk}', inner, '', 'data-i18n-html'])
    m = re.search(r'const KEYED_JA = \{(.*?)\n  \};', js, re.S)
    if m:
        for k, v in re.findall(r"'([\w.]+)': '((?:[^'\\]|\\.)*)'", m.group(1)):
            S['html'].append([f'html.{k}', v.replace("\\'", "'"), '', 'JS'])
    # データ
    def block(id):
        mm = re.search(r'<script[^>]*id="%s"[^>]*>(.*?)</script>' % id, src, re.S); return json.loads(mm.group(1))
    cfg = block('tcbf-config')
    for k in ('eventName', 'eventDate', 'hashtags'):
        S['config'].append([f'config.{k}', cfg.get(k, ''), '', ''])
    for i, a in enumerate(block('tcbf-axes')):
        S['axes'].append([f'axes.{i}.name', a['name'], '', '軸の名前'])
        S['axes'].append([f'axes.{i}.left', a['left']['word'], '', f"左の極 {a['left']['code']}"])
        S['axes'].append([f'axes.{i}.right', a['right']['word'], '', f"右の極 {a['right']['code']}"])
    for mm in re.finditer(r'<article class="type-card" data-code="(\w+)">(.*?)</article>', body, re.S):
        code, inner = mm.group(1), mm.group(2)
        g = lambda cls: re.search(r'<p class="%s">(.*?)</p>' % cls, inner, re.S).group(1).strip()
        S['types'].append([f'types.{code}.name', g('name'), '', 'タイプ名'])
        S['types'].append([f'types.{code}.catch', g('catch'), '', 'キャッチ'])
        S['types'].append([f'types.{code}.desc', g('desc'), '', '説明'])
        for i, li in enumerate(re.findall(r'<li>(.*?)</li>', re.search(r'<ul class="styles">(.*?)</ul>', inner, re.S).group(1))):
            S['types'].append([f'types.{code}.styles.{i}', li.strip(), '', 'スタイル'])
        S['types'].append([f'types.{code}.hint', re.search(r'<span class="hint-text">(.*?)</span>', inner, re.S).group(1).strip(), '', '会場でのヒント'])
    for b in block('tcbf-beers'):
        for k in ('brewery', 'beer', 'style'):
            if b.get(k): S['beers'].append([f'beers.{b["no"]}.{k}', b[k], '', ''])
    for b in block('tcbf-brewers'):
        for k in ('brewery', 'company', 'location', 'beer', 'style', 'pr', 'aroma', 'food', 'pour', 'story', 'region', 'trivia'):
            if b.get(k): S['brewers'].append([f'brewers.{b["no"]}.{k}', b[k], '', b['brewery'] if k != 'brewery' else ''])
    zk = block('tcbf-zukan')
    for c in zk['chars']:
        n = c['no']; w = f"No.{n:02d} {c['name']}"
        for k in ('cls', 'me', 'look', 'persona', 'home', 'food', 'dislike', 'zukan'):
            S['zukan'].append([f'zukan.{n}.{k}', c[k], '', w])
        for i, v in enumerate(c['ability']): S['zukan'].append([f'zukan.{n}.ability.{i}', v, '', w])
        for i, mv in enumerate(c['moves']):
            for j, v in enumerate(mv): S['zukan'].append([f'zukan.{n}.moves.{i}.{j}', v, '', w])
        for k in ('kuchiguse', 'kime'): S['zukan'].append([f'zukan.{n}.{k}', c[k], '', w])
        for i, v in enumerate(c['lines']): S['zukan'].append([f'zukan.{n}.lines.{i}', v, '', w])
        for k in ('trivia', 'neta'):
            if c.get(k): S['zukan'].append([f'zukan.{n}.{k}', c[k], '', w])
    for kind in ('friends', 'rivals'):
        for i, p in enumerate(zk[kind]):
            S['zukan'].append([f'zukan.{kind}.{i}', p[2], '', f'{p[0]} と {p[1]}'])
    m = re.search(r'const STORY_JA = \[(.*?)\n  \];', js, re.S)
    for i, (t, x) in enumerate(re.findall(r"\{ t: '((?:[^'\\]|\\.)*)', x: '((?:[^'\\]|\\.)*)' \}", m.group(1)), 1):
        S['story'].append([f'story.{i}.t', t.replace("\\'", "'"), '', f'P{i} 見出し'])
        S['story'].append([f'story.{i}.x', x.replace("\\'", "'"), '', f'P{i} 本文'])
    m = re.search(r'const ODAI_JA = \[(.*?)\n  \];', js, re.S)
    for i, s in enumerate(re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))):
        S['odai'].append([f'odai.{i}', s.replace("\\'", "'"), '', ''])
    return S


def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass
    args = sys.argv[1:]
    fills = {}
    if '--fill' in args:
        for p in args[args.index('--fill') + 1:]:
            fills.update(json.loads(Path(p).read_text(encoding='utf-8')))
    src = SRC.read_text(encoding='utf-8')
    S = extract(src)
    OUT.mkdir(exist_ok=True)
    # 既存の EN を保持（JA が同じ行だけ）
    old = {}
    for f in FILES:
        p = OUT / f
        if p.exists():
            for sec, rows in parse_md(p.read_text(encoding='utf-8')).items():
                for key, ja, en, where in rows: old[(sec, key)] = (ja, en)
    total = 0; filled = 0
    for f, secs in FILES.items():
        parts = []
        for sec in secs:
            rows = S[sec]
            for r in rows:
                o = old.get((sec, r[0]))
                if o and o[0] == r[1] and o[1]: r[2] = o[1]
                v = fills.get(r[0]) or (fills.get(r[1]) if sec == 'ui' else None)
                if v:
                    if v.startswith('?'): v = v[1:].strip(); r[3] = (r[3] + ' ' if r[3] else '') + '← 要確認'
                    r[2] = v
                total += 1; filled += bool(r[2])
            parts.append((sec, rows))
        write_md(OUT / f, parts, f'# 英訳の確認用一覧：{f}\n\n'
                 '書き方：EN の欄を直接直してください。空欄のままの項目は日本語のまま表示されます。'
                 'EN を「=」にすると日本語（ラテン文字の固有名詞など）をそのまま使います。'
                 '{n} のような {…} と <br> <b> は残してください。表のセルに | は使えません（｜ を使う）。')
    print(f'rows {total}, EN filled {filled}')
    for sec, rows in S.items(): print(f'  {sec}: {len(rows)}')


if __name__ == '__main__':
    main()

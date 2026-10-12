# -*- coding: utf-8 -*-
"""i18n/*.md（確認用一覧）の EN を集めて i18n/en.json を作り、index.html の #tcbf-i18n に埋め込む。

検証：キーの過不足、{…} の差し込みの一致、タグ入り以外に < が無いこと、JSON として読めること、node --check
使い方:  python -I tools/i18n_build.py [--check-only]
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n_extract import FILES, SRC, OUT, extract, parse_md  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
JP = re.compile(r'[぀-ヿ㐀-鿿]')


def collect():
    rows = {}   # (section, key) -> (ja, en)
    for f, secs in FILES.items():
        p = OUT / f
        if not p.exists():
            continue
        for sec, lst in parse_md(p.read_text(encoding='utf-8')).items():
            for key, ja, en, where in lst:
                rows[(sec, key)] = (ja, en)
    return rows


def en_value(ja, en):
    en = (en or '').strip()
    if not en:
        return None
    if en == '=':
        return ja
    return en


def build(rows, current):
    """current: 抽出したいまの一覧（キーと JA の正）。rows: md の内容"""
    d = {'ui': {}, 'html': {}, 'config': {}, 'axes': [], 'types': {}, 'beers': {}, 'brewers': {}, 'zukan': {'chars': {}, 'friends': [], 'rivals': []}, 'story': [], 'odai': []}
    problems, missing = [], []
    for sec, lst in current.items():
        for key, ja, _en, _w in lst:
            r = rows.get((sec, key))
            if r is None or r[0] != ja:
                missing.append(f'{sec}: {key}' + ('（JA が変わっています）' if r else '')); continue
            en = en_value(ja, r[1])
            if en is None:
                missing.append(f'{sec}: {key}'); continue
            # 差し込み {x} は JA にあるものが EN にも必要
            pj = set(re.findall(r'\{(\w+)\}', ja)); pe = set(re.findall(r'\{(\w+)\}', en))
            if pj - pe: problems.append(f'{sec}: {key}: 差し込み {sorted(pj - pe)} が EN にありません')
            if sec != 'html' and '<' in en and '<' not in ja: problems.append(f'{sec}: {key}: EN にタグ（<）があります')
            if sec == 'ui':
                d['ui'][ja] = en
            elif sec == 'html':
                d['html'][key[len('html.'):]] = en
            elif sec == 'config':
                d['config'][key.split('.', 1)[1]] = en
            elif sec == 'axes':
                _, i, field = key.split('.'); i = int(i)
                while len(d['axes']) <= i: d['axes'].append({})
                d['axes'][i][field] = en
            elif sec == 'types':
                _, code, field, *rest = key.split('.')
                t = d['types'].setdefault(code, {})
                if field == 'styles':
                    t.setdefault('styles', []); i = int(rest[0])
                    while len(t['styles']) <= i: t['styles'].append('')
                    t['styles'][i] = en
                else:
                    t[field] = en
            elif sec in ('beers', 'brewers'):
                _, no, field = key.split('.')
                d[sec].setdefault(no, {})[field] = en
            elif sec == 'zukan':
                parts = key.split('.')
                if parts[1] in ('friends', 'rivals'):
                    i = int(parts[2]); lst2 = d['zukan'][parts[1]]
                    while len(lst2) <= i: lst2.append('')
                    lst2[i] = en
                else:
                    no, field = parts[1], parts[2]
                    c = d['zukan']['chars'].setdefault(no, {})
                    if field == 'ability':
                        c.setdefault('ability', ['', '']); c['ability'][int(parts[3])] = en
                    elif field == 'moves':
                        c.setdefault('moves', [['', ''], ['', ''], ['', '']]); c['moves'][int(parts[3])][int(parts[4])] = en
                    elif field == 'lines':
                        c.setdefault('lines', []); i = int(parts[3])
                        while len(c['lines']) <= i: c['lines'].append('')
                        c['lines'][i] = en
                    else:
                        c[field] = en
            elif sec == 'story':
                _, i, field = key.split('.'); i = int(i) - 1
                while len(d['story']) <= i: d['story'].append({})
                d['story'][i][field] = en
            elif sec == 'odai':
                i = int(key.split('.')[1])
                while len(d['odai']) <= i: d['odai'].append('')
                d['odai'][i] = en
    # 絵本：英語ページは12ページそろったときだけ使う（途中なら日本語ページのまま）
    if len(d['story']) != 12 or any(not p.get('t') or not p.get('x') for p in d['story']):
        d['story'] = []
    # 未訳の配列要素は空のまま → アプリ側で日本語にフォールバック
    for key in list(d.keys()):
        if d[key] in ({}, []):
            del d[key]
    return d, problems, missing


def inject(html, data):
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    pat = re.compile(r'(<script type="application/json" id="tcbf-i18n">)(.*?)(</script>)', re.S)
    assert pat.search(html), '#tcbf-i18n が見つかりません'
    return pat.sub(lambda m: m.group(1) + js + m.group(3), html, count=1), len(js.encode('utf-8'))


def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass
    check_only = '--check-only' in sys.argv
    html = SRC.read_text(encoding='utf-8')
    current = extract(html)
    rows = collect()
    data, problems, missing = build(rows, current)
    total = sum(len(v) for v in current.values())
    print(f'rows {total}, missing EN {len(missing)}, problems {len(problems)}')
    for m in missing[:30]: print('  missing:', m)
    if len(missing) > 30: print(f'  … ほか {len(missing) - 30} 件')
    for p in problems: print('  PROBLEM:', p)
    if problems:
        sys.exit(1)
    (OUT / 'en.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    if check_only:
        return
    html2, size = inject(html, data)
    SRC.write_text(html2, encoding='utf-8', newline='\n')
    print(f'injected #tcbf-i18n: {size:,} bytes; index.html {len(html2.encode("utf-8")):,} bytes')
    # JSON ブロックが読めるか、スクリプトの構文
    m = re.search(r'<script type="application/json" id="tcbf-i18n">(.*?)</script>', html2, re.S)
    json.loads(m.group(1).replace('<\\/', '</'))
    i = html2.rindex('<script>') + len('<script>'); j = html2.index('</script>', i)
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(html2[i:j]); tmp = f.name
    r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    print('node --check:', 'OK' if r.returncode == 0 else r.stderr[:800])
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()

# ビールタイプ診断（beer meets Design）

つくばクラフトビアフェスト 2026（2026年10月16日〜18日・つくばセンター広場）の当日企画「Beer meets Design」の診断アプリです。
8問の質問で、飲み口・苦み・香り・原料の4軸から16タイプを判定し、相性のよいスタイル・真逆のタイプ・会場で出会えるフラッグシップビール・ビアキャラ図鑑・絵本を案内します。

- 公開ページ: https://tsukuba-craft-beer-fest.github.io/tcbf2026-beer-meets-design/ （GitHub Pages。このリポジトリの `index.html`）
- 英語版: 上記に `?lang=en` を付けて開く（例 https://tsukuba-craft-beer-fest.github.io/tcbf2026-beer-meets-design/?lang=en ）。ヘッダーの「EN／日本語」ボタンでも切り替えられます
- 旧URL https://gon-naokin.github.io/tcbf2026-shindan/ は上記へ自動転送されます
- 構成: 単一の HTML ファイル。画像・データはすべて内包し、サーバー処理はありません（ページ画像だけ `assets/`）
- 更新方法: `index.html` を差し替えて `main` に push すると、数分で反映されます

## 英語版の仕組みと直し方

- 日本語が正本です。英語は `index.html` 内の `<script id="tcbf-i18n">` にある辞書で上書きし、辞書に無い文言は日本語のまま表示されます
- 英訳は `i18n/*.md`（日本語｜英語の一覧）で管理します。英文を直したら次を実行して `index.html` に埋め込みます
  - `python -I tools/i18n_build.py`
- 日本語の文言を変えたら、一覧を作り直してから埋め込みます（既存の英訳は保持されます）
  - `python -I tools/i18n_extract.py` → 変わった行の EN を書く → `python -I tools/i18n_build.py`
- 絵本の英語ページは `TCBF2026_BmD_3Dマガジン/src/magazine_en.html` から書き出し、`assets/story/en/` に置きます
  - `python -I render.py <作業フォルダ> --html magazine_en.html --prefix EN_P` → `python -I to_app.py .. EN_P <このリポジトリ>/assets/story/en`

協力　筑波技術大学

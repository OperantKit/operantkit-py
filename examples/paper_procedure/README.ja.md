# 論文の手続き

:gb: [English](README.md)

公刊された実験の手続きを DOI から走らせる。スクリプトは `papers.json` で DOI を引き、論文の Method 節から取り出した contingency-dsl の文字列を仮想被験体で走らせ、累積記録を描き、論文が報告している定性的なパターンが出たかを判定する。比べるのは定性的なパターンだけで、論文の数値とは比べない。

## 実行

```bash
pip install operantkit
python examples/paper_procedure/run.py --doi 10.1016/j.beproc.2004.08.007
```

スクリプトは `run.py` と同じフォルダに次を書く。

- `<slug>.okl` — OKL v1 のイベントログ
- `<slug>.png` — 累積記録

そして JSON の報告を出す: DSL、比べる図、期待パターン、指標、一致したか（`judgement.matched`）。

| オプション | 意味 |
|---|---|
| `--control` | 一定率（1 Hz）のポアソン被験体で走らせる。判定は不一致になるはず |
| `--dsl-dir DIR` | `papers.json` の代わりに、DOI を名前にした生成 DSL ファイル（`/` を `_` に置き換え、拡張子 `.dsl`）のフォルダから DSL を読む |
| `--block N` または `--block <スケジュール>` | 複数ブロックの DSL ファイルから 1 つを選ぶ。1 始まりの番号か、ブロックのスケジュール行（例: `FR40`） |
| `--out-dir DIR`、`--seed N` | 出力先と被験体の seed |

## カタログ

`papers.json` は DOI ごとに次を持つ: APA 形式の書誌、取り出した DSL、図と期待パターン（言い換え）、仮想被験体、強化回数、強化子の継続時間、判定。論文の図は写していない。

| DOI | DSL | 図 | 期待パターン | 被験体 | 判定 |
|---|---|---|---|---|---|
| 10.1016/j.beproc.2004.08.007 | `FI30s` | Fig. 2 | 各区間の初めは反応が少なく、区間が進むにつれて反応率が上がる | `ScallopSubject`（2 Hz・ramp 30 s・指数 2） | `rate_rises_within_interval` |

判定 `rate_rises_within_interval` は、1 つの強化子の終了から次の強化子までを 1 区間とする。区間の後半の反応数が前半より多い区間が 80% 以上あり、quarter-life（session-analyzer の `compute_quarter_life`）の中央値が 0.4 以上なら一致とする。一定率なら quarter-life は 0.25 付近になる。

## 結果（seed 2004）

![FI 30-s・強化 30 回の累積記録](higa_simm_2004.png)

| 被験体 | 反応数 | 後半の反応が多い区間 | quarter-life の中央値 | 判定 |
|---|---|---|---|---|
| `ScallopSubject` | 640 | 30 区間中 30 | 0.64 | 一致 |
| ポアソン対照（1 Hz） | 904 | 30 区間中 14 | 0.21 | 不一致 |

`tests/test_paper_procedure.py` がコマンドを走らせ、PNG が書かれること、`ScallopSubject` が一致し対照が一致しないこと、seed を固定すると OKL ログがバイト単位で一致すること、生成 DSL ファイルから DSL のブロックを取り出せることを確かめる。

## 論文の手続きとの違い

論文では強化子は 20 秒間の鏡像の提示で、次の区間は強化子の終了から測る。contingency-py は定間隔を強化子の開始から測るので、20 秒の強化子では強化子の後に区間が 10 秒しか残らない。そのためカタログでは強化子を 0.5 秒にして、強化子の後の区間を 30 秒近くに保っている。

## 出典

- Higa, J. J., & Simm, L. A. (2004). Interval timing in Siamese fighting fish (*Betta splendens*). *Behavioural Processes*, *67*, 501–509. https://doi.org/10.1016/j.beproc.2004.08.007

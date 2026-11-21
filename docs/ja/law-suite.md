# 法則スイート: 法則 × 被験体

:gb: [English](../en/law-suite.md)

`tests/laws/` は experiment-io の仮想被験体を文献の手続きで走らせ、記録を原典の報告値（各検査ファイルに引用）と照らして判定する。このページは `.venv/bin/python tests/laws/law_table.py` が、検査が assert するのと同じ関数から生成する（各 10 seed。値は seed 間の中央値 [最小, 最大]）。古くなると `tests/laws/test_law_table.py` が落ちる。

- **予測する**: 被験体の原典が、その法則が成り立つと述べている。検査が落ちればテストの失敗。ただし *xfail* と書いた検査は、理由を付けて strict な想定内の失敗として記録する。
- **対照**: 一定の率のポアソン反応体。法則を満たしてはならない（各法則の対照の検査が判定する。法則の検査の値は参考に載せる）。
- **対象外**: 走らせない。被験体に、その手続きに当てる式が無い。

`RaCSubject`（Shahan & Craig, 2017）と `MprSubject`（Killeen, 1994）は公表されたパラメータの値を使い、これらの検査に合わせた値ではない。比率と時隔の比較では、`MprSubject` の比率の側はラットの VR の公表値、時隔の側はハトの FI の公表値を使う（両方を同じ個体群で測った値は見つからなかった）。理由の文は検査のコードの英語をそのまま写している。

## FI スキャロップ（`test_fi_scallop.py`、FI 60-s）

| 被験体 | 期待 | 検査 | 想定 | 結果 | 値 |
|---|---|---|---|---|---|
| `VirtualSubject` | 対照 | F1: breakpoint 0.67 ± 0.15 (Schneider, 1969) | — | 落ちる | 0.367 [0.200, 0.470] |
| `VirtualSubject` | 対照 | F2: share of rising segment steps ≥ 0.74 (Dews, 1978) | — | 落ちる | 0.448 [0.407, 0.485] |
| `VirtualSubject` | 対照 | F2aux: 5th / 1st segment rate ≥ 2 (Dews, 1978) | — | 落ちる | 0.954 [0.792, 1.167] |
| `VirtualSubject` | 対照 | F3: index of curvature ≥ 0.56 (Fry et al., 1960) | — | 落ちる | 0.001 [-0.021, 0.020] |
| `VirtualSubject` | 対照 | F4: peak in the last 3 of 10 segments in ≥ 24 of 30 intervals (Lowe & Harzem, 1977) | — | 落ちる | 7.000 [6.000, 11.000] |
| `ScallopSubject` | 予測する | F1: breakpoint 0.67 ± 0.15 (Schneider, 1969) | 通る | 通る | 0.750 [0.745, 0.765] |
| `ScallopSubject` | 予測する | F2: share of rising segment steps ≥ 0.74 (Dews, 1978) | 通る | 通る | 0.845 [0.806, 0.911] |
| `ScallopSubject` | 予測する | F2aux: 5th / 1st segment rate ≥ 2 (Dews, 1978) | 通る | 通る | 7.836 [6.949, 8.613] |
| `ScallopSubject` | 予測する | F3: index of curvature ≥ 0.56 (Fry et al., 1960) | 通る | 通る | 0.638 [0.630, 0.646] |
| `ScallopSubject` | 予測する | F4: peak in the last 3 of 10 segments in ≥ 24 of 30 intervals (Lowe & Harzem, 1977) | 通る | 通る | 30.000 [30.000, 30.000] |
| `SpacedRespondingSubject` | 対象外 | — | — | — | — |
| `IrtCopyistSubject` | 対象外 | — | — | — | — |
| `MatchingSubject` | 対象外 | — | — | — | — |
| `RaCSubject` | 対象外 | — | — | — | — |
| `MprSubject` | 予測する | F1: breakpoint 0.67 ± 0.15 (Schneider, 1969) | xfail | 落ちる | 0.506 [0.500, 0.530] |
| `MprSubject` | 予測する | F2: share of rising segment steps ≥ 0.74 (Dews, 1978) | xfail | 落ちる | 0.488 [0.438, 0.544] |
| `MprSubject` | 予測する | F2aux: 5th / 1st segment rate ≥ 2 (Dews, 1978) | xfail | 落ちる | 1.123 [1.059, 1.926] |
| `MprSubject` | 予測する | F3: index of curvature ≥ 0.56 (Fry et al., 1960) | xfail | 落ちる | 0.497 [0.481, 0.511] |
| `MprSubject` | 予測する | F4: peak in the last 3 of 10 segments in ≥ 24 of 30 intervals (Lowe & Harzem, 1977) | xfail | 落ちる | 17.000 [12.000, 24.000] |

理由:

- `VirtualSubject` (対照): constant-rate Poisson responder (two of them on concurrent VI VI)
- `ScallopSubject` (予測する): rate rises with time since reinforcement (fourth power, CV 0.3)
- `SpacedRespondingSubject` (対象外): built for the DRL example (spaced responding); no law in this suite tests it
- `IrtCopyistSubject` (対象外): copies reinforced IRTs; this suite runs it on ratio versus interval only
- `MatchingSubject` (対象外): two-operandum subject
- `RaCSubject` (対象外): two-operandum model; with one operandum its rate is a function of the reinforcement rate only (Shahan & Craig, 2017)
- `MprSubject` (予測する): a pause of about half the interval, then a constant run rate (Killeen, 1994): a two-state pattern, not a gradual acceleration
  - F1 (xfail): the pause is half the interval (Killeen, 1994, 'about half'); the check's source puts the break at two-thirds (Schneider, 1969), and 0.5 is below its lower edge 0.52
  - F2 (xfail): needs a rate that keeps rising; MPR runs at a constant rate after the pause
  - F2aux (xfail): needs a rate that keeps rising; MPR runs at a constant rate after the pause
  - F3 (xfail): a pause of half the interval at a constant rate gives an index of 0.5 (< 0.56)
  - F4 (xfail): a constant run rate puts the peak in any of the last five segments, not mostly in the last three

## VR とヨークした VI（`test_ratio_vs_interval.py`、VR 25）

| 被験体 | 期待 | 検査 | 想定 | 結果 | 値 |
|---|---|---|---|---|---|
| `VirtualSubject` | 対照 | V1: VR / yoked VI rate > 1 in every pair, median ≥ 1.5 (Catania et al., 1977) | — | 落ちる | 1.007 [0.977, 1.033] |
| `VirtualSubject` | 対照 | V2: yoked VI < 300 reinforcers/h (Baum, 1993) | — | 通る | 136.272 [133.210, 138.232] |
| `VirtualSubject` | 対照 | V3: rate ratio falls to 1.1 at 300–600 reinforcers/h (Baum, 1993) | — | 落ちる | 17.529 [17.411, inf] |
| `ScallopSubject` | 対象外 | — | — | — | — |
| `SpacedRespondingSubject` | 対象外 | — | — | — | — |
| `IrtCopyistSubject` | 予測する | V1: VR / yoked VI rate > 1 in every pair, median ≥ 1.5 (Catania et al., 1977) | 通る | 通る | 1.821 [1.264, 2.213] |
| `IrtCopyistSubject` | 予測する | V2: yoked VI < 300 reinforcers/h (Baum, 1993) | 通る | 通る | 126.864 [83.854, 186.221] |
| `IrtCopyistSubject` | 予測する | V3: rate ratio falls to 1.1 at 300–600 reinforcers/h (Baum, 1993) | xfail | 落ちる | inf [inf, inf] |
| `MatchingSubject` | 対象外 | — | — | — | — |
| `RaCSubject` | 対象外 | — | — | — | — |
| `MprSubject` | 予測する | V1: VR / yoked VI rate > 1 in every pair, median ≥ 1.5 (Catania et al., 1977) | 通る | 通る | 1.524 [1.476, 1.617] |
| `MprSubject` | 予測する | V2: yoked VI < 300 reinforcers/h (Baum, 1993) | xfail | 落ちる | 483.747 [480.072, 488.962] |
| `MprSubject` | 予測する | V3: rate ratio falls to 1.1 at 300–600 reinforcers/h (Baum, 1993) | xfail | 落ちる | inf [inf, inf] |

理由:

- `VirtualSubject` (対照): constant-rate Poisson responder (two of them on concurrent VI VI)
- `ScallopSubject` (対象外): its rate ramp is tied to a fixed interval (ramp_s)
- `SpacedRespondingSubject` (対象外): built for the DRL example (spaced responding); no law in this suite tests it
- `IrtCopyistSubject` (予測する): emits the inter-response times that were reinforced (Tanno & Silberberg, 2012)
  - V3 (xfail): the copyist's VR / yoked VI rate ratio stays at 1.5-2.1 up to about 1,100 reinforcers per hour and never falls to 1.1 (Baum: 300-600)
- `MatchingSubject` (対象外): two-operandum subject
- `RaCSubject` (対象外): rate is a function of the reinforcement rate only, so equal reinforcement rates give equal response rates
- `MprSubject` (予測する): interval schedules command lower rates than ratio schedules (Killeen, 1994); ratio parameters are the published rat VR values, interval parameters the published pigeon FI values (not one population)
  - V2 (xfail): not predicted: the rat VR values give about 218 responses/min on VR 25, so the yoked VI earns about 480 reinforcers/h, above the check's 300
  - V3 (xfail): not predicted: the ratio stays at 1.26-1.57 from 100 to 3,550 reinforcers/h and falls below 1 only at VR 200 (ratio strain), so it never converges from above

## 一般化マッチング（`test_matching.py`、並立 VI VI）

| 被験体 | 期待 | 検査 | 想定 | 結果 | 値 |
|---|---|---|---|---|---|
| `VirtualSubject` | 対照 | M1: sensitivity 0.83 ≤ a ≤ 1.11 (Baum, 1979) | — | 落ちる | -0.005 [-0.045, 0.047] |
| `VirtualSubject` | 対照 | M2: \|relative responses − relative reinforcers\| ≤ 0.10 (Herrnstein, 1961) | — | 落ちる | 0.189 [0.018, 0.355] |
| `ScallopSubject` | 対象外 | — | — | — | — |
| `SpacedRespondingSubject` | 対象外 | — | — | — | — |
| `IrtCopyistSubject` | 対象外 | — | — | — | — |
| `MatchingSubject` | 予測する | M1: sensitivity 0.83 ≤ a ≤ 1.11 (Baum, 1979) | 通る | 通る | 0.938 [0.903, 0.989] |
| `MatchingSubject` | 予測する | M2: \|relative responses − relative reinforcers\| ≤ 0.10 (Herrnstein, 1961) | 通る | 通る | 0.008 [0.001, 0.016] |
| `RaCSubject` | 予測する | M1: sensitivity 0.83 ≤ a ≤ 1.11 (Baum, 1979) | xfail | 落ちる | 0.840 [0.734, 0.876] |
| `RaCSubject` | 予測する | M2: \|relative responses − relative reinforcers\| ≤ 0.10 (Herrnstein, 1961) | 通る | 通る | 0.012 [0.000, 0.063] |
| `MprSubject` | 対象外 | — | — | — | — |

理由:

- `VirtualSubject` (対照): constant-rate Poisson responder (two of them on concurrent VI VI)
- `ScallopSubject` (対象外): single-operandum subject; the law needs two operanda
- `SpacedRespondingSubject` (対象外): built for the DRL example (spaced responding); no law in this suite tests it
- `IrtCopyistSubject` (対象外): single-operandum subject; the law needs two operanda
- `MatchingSubject` (予測する): melioration: shifts responses toward the key with the higher local reinforcement rate (Herrnstein & Vaughan, 1980)
- `RaCSubject` (予測する): B_T / B_Alt = b V_T / V_Alt with b = 1: sensitivity 1 when the values equal the arranged rates (Shahan & Craig, 2017; Shahan, Browning, & Nall, 2020)
  - M1 (xfail): undermatches: sensitivity 0.84 [0.73, 0.88] with ten sessions per condition and 0.85 [0.82, 0.89] with thirty. A likely cause, not verified: the values weight every session since the option was first reinforced, so the earlier conditions stay in them
- `MprSubject` (対象外): single-operandum subject; the law needs two operanda

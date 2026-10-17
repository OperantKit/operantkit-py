# Concurrent VI VI matching

:jp: [日本語版](README.ja.md)

Reproduces the matching relation reported by Herrnstein (1961): on two concurrent variable-interval (VI) schedules with a changeover delay (COD), the relative frequency of responding on a key approximately equals the relative frequency of reinforcement on that key.

## Run

```bash
pip install operantkit
python examples/concurrent_vi_matching/run.py
```

The script runs Herrnstein's four pairs of schedules, each with a 1.5-s COD, and writes, next to `run.py`:

- `concurrent_vi_matching_<condition>.okl` — the OKL v1 event log of the last session of each condition
- `concurrent_vi_matching.png` — relative responses on key A against relative reinforcement on key A, with the diagonal (perfect matching)

and prints the per-condition counts, the proportions, and the generalized matching law fit. `python examples/concurrent_vi_matching/run.py --no-cod` runs the same conditions without the COD and writes into `no_cod/`.

The example needs two pieces that are newer than the first PyPI releases:

- contingency-py with the reinforcer-holding COD (a reinforcer set up during the COD is kept for its key and delivered by the first response after the COD). With a contingency-py whose COD discards that reinforcer, the subject falls into exclusive preference and the fit fails. Install contingency-py from <https://github.com/OperantKit/contingency-py> if the installed version discards it.
- `MatchingSubject` from experiment-io. Install experiment-io from <https://github.com/OperantKit/experiment-io> if the installed version does not provide it.

## What runs

Each condition is a contingency-dsl string such as

```
@algorithm("fleshler-hoffman", n=12, seed=1975)
Conc(VI 135-s, VI 270-s, COD=1.5-s)
```

parsed by contingency-dsl, turned into the contingency-py `Concurrent` schedule, and run by session-runner. experiment-io's `drive()` feeds the virtual subject's responses into the session and writes every event to the OKL log through session-recorder. A session ends after 60 reinforcers; each reinforcer lasts 4 s.

| Condition | Key A | Key B |
|---|---|---|
| `vi180_vi180` | VI 180 s | VI 180 s |
| `vi135_vi270` | VI 135 s | VI 270 s |
| `vi108_vi540` | VI 108 s | VI 540 s |
| `vi90_ext` | VI 90 s | EXT |

Every pair gives 40 reinforcers per hour in total. Each condition runs five sessions with one subject (a new subject per condition); each session draws a new Fleshler-Hoffman sequence. Only the last session is analysed.

The subject is experiment-io's `MatchingSubject` (`stay=0.9`, other parameters at their defaults). It responds at 1 Hz, keeps for each key a moving average of reinforcers per response on that key, and moves its response allocation toward the key whose average is higher (melioration). Matching is not written into the subject: the allocation stops moving where reinforcers per response are equal on both keys, and whether that point is reached depends on the schedule.

## Result (seed 1961)

![Relative responses against relative reinforcement on key A](concurrent_vi_matching.png)

| Condition | Responses A / B | Reinforcers A / B | Relative responses on A | Relative reinforcement on A |
|---|---|---|---|---|
| `vi180_vi180` | 3190 / 3513 | 32 / 28 | 0.476 | 0.533 |
| `vi135_vi270` | 4534 / 1650 | 43 / 17 | 0.733 | 0.717 |
| `vi108_vi540` | 4871 / 873 | 53 / 7 | 0.848 | 0.883 |
| `vi90_ext` | 5146 / 48 | 60 / 0 | 0.991 | 1.000 |

The largest difference between relative responses and relative reinforcement is 0.057. The generalized matching law, log(B_A / B_B) = a · log(R_A / R_B) + log b, fitted over the three conditions that reinforce both keys (session-analyzer's `estimate_matching_parameters`), gives a = 0.94, log b = −0.09, R² = 0.95.

`tests/test_examples.py` checks that a is between 0.8 and 1.2 and R² is above 0.9, that every condition differs by at most 0.10, and that a fixed seed reproduces the OKL logs byte for byte.

With other seeds (1, 2, 3, 7, 42, 100) the largest difference stayed at or below 0.055, but a ranged from 0.68 to 1.23. The fit uses three points from one 60-reinforcer session each, so a is the least stable of these measures.

### Not reproduced: the effect of removing the COD

Herrnstein reports that without the COD, at about 66% reinforcement on key A, two pigeons responded 50% and 56% on key A, outside the range seen with the COD. This example does not reproduce that departure. With `--no-cod` (seed 1961) the largest difference is 0.052 and a = 0.91. Herrnstein attributes the effect to switching acting as a third operant that is reinforced when the first peck after a changeover produces food; `MatchingSubject` has no switching response whose rate can change with reinforcement, so removing the COD changes little here.

## Differences from the original procedure

- Herrnstein ran 17 to 44 sessions per condition with the same pigeons throughout and pooled the last five sessions. This example runs five sessions per condition, a new subject per condition, and analyses the last session only.
- The subject is a simulated responder at 1 Hz, not a pigeon; absolute response rates are not comparable.

## Source

Herrnstein's Method: "Each time a peck to one key followed a peck to the other key, no reinforcement was possible for 1.5 seconds. … At least two consecutive pecks on a given key were necessary before reinforcement was possible." The pairs of values were VI 3 min VI 3 min, VI 2.25 min VI 4.5 min, VI 1.8 min VI 9 min, and VI 1.5 min with extinction on the other key; the reinforcer was 4 s of access to grain; sessions lasted for 60 reinforcements. The relative frequencies of responding matched those of reinforcement "with a maximum discrepancy of only about 8%".

- Herrnstein, R. J. (1961). Relative and absolute strength of response as a function of frequency of reinforcement. *Journal of the Experimental Analysis of Behavior, 4*(3), 267–272. https://doi.org/10.1901/jeab.1961.4-267

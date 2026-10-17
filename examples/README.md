# Examples: classic experiments

:jp: [日本語版](README.ja.md)

Each example reproduces the behavioral pattern of a classic experiment with a virtual subject, using only the public OperantKit pipeline: a contingency-dsl string, the contingency-py schedule it compiles to, session-runner, experiment-io's `drive()`, and an OKL v1 log analyzed by session-analyzer. Only the subject is specific to each example; it receives the reinforcers the schedule delivers and knows nothing about the schedule itself.

## Run

```bash
pip install operantkit
python examples/<name>/run.py
```

Each `run.py` runs without arguments and writes its OKL log and figures next to itself. Session time is simulated, so a run takes seconds, and a fixed seed reproduces the OKL log byte for byte. The subjects are in experiment-io; if the installed experiment-io does not provide them, install it from <https://github.com/OperantKit/experiment-io>. `tests/test_examples.py` runs every example and checks its pattern.

## Examples

| Example | Experiment | Primary source | DSL | Command | Figures |
|---|---|---|---|---|---|
| [fi_scallop](fi_scallop/README.md) | Fixed-interval scallop: a pause after each reinforcer, then accelerating responding | Ferster & Skinner (1957) | `FI 60-s` | `python examples/fi_scallop/run.py` | Cumulative record |
| [concurrent_vi_matching](concurrent_vi_matching/README.md) | Matching on concurrent VI VI: relative responses track relative reinforcement | Herrnstein (1961) | `Conc(VI 180-s, VI 180-s, COD=1.5-s)` and three more pairs | `python examples/concurrent_vi_matching/run.py` | Relative responses against relative reinforcement, with the diagonal |
| [drl_irt](drl_irt/README.md) | Differential reinforcement of low rate: IRTs lengthen and the rate falls | Ferster & Skinner (1957) | `DRL 10-s` | `python examples/drl_irt/run.py` | IRT histograms (first and last 600 s); IRT-coded cumulative record |

## Sources

- Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000
- Herrnstein, R. J. (1961). Relative and absolute strength of response as a function of frequency of reinforcement. *Journal of the Experimental Analysis of Behavior*, *4*(3), 267–272. https://doi.org/10.1901/jeab.1961.4-267

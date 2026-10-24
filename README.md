# operantkit

:jp: [日本語版 README](README.ja.md)

`operantkit` is the package that installs the core [OperantKit](https://github.com/OperantKit) libraries and the `operant` command together, and this repository (operantkit-py) also holds the worked examples that rerun classic experiments on simulated subjects. It contains no code of its own. Start here if you want to see what OperantKit does on a familiar result before using the individual packages.

- **Classic results, rerun end to end:** the FI scallop, DRL responding, and concurrent VI VI matching, each from a schedule expression to an event log and a figure.
- **Everything is the public pipeline:** only the simulated subject is specific to each example.
- **Reproducible:** session time is simulated and every draw is seeded, so a run writes the same logs every time.

## Installation

Python 3.11 or newer. The OperantKit packages are not on PyPI yet, so `pip install operantkit` and `pip install git+https://github.com/OperantKit/operantkit-py` both fail while resolving dependencies. Install the libraries from GitHub without dependency resolution, then add the three third-party libraries they need:

```bash
G=git+https://github.com/OperantKit
pip install --no-deps $G/contingency-dsl-py $G/contingency-py $G/experiment-core \
  $G/session-recorder $G/session-runner $G/session-analyzer $G/experiment-io $G/operantkit-cli
pip install numpy scipy matplotlib
```

This is exactly the set the meta-package depends on. `pip check` reports version mismatches between these development builds; they do not affect the examples. For a serial-port device, also `pip install pyserial`.

## Example

Clone this repository and rerun Herrnstein's (1961) concurrent VI VI conditions:

```bash
git clone https://github.com/OperantKit/operantkit-py
cd operantkit-py
python examples/concurrent_vi_matching/run.py
```

It runs four pairs of variable-interval (VI) schedules, each with a 1.5-s changeover delay, for example `Conc(VI 135-s, VI 270-s, COD=1.5-s)`, on a simulated subject that shifts its responding toward the richer key. It writes one OKL (OperantKit Log) event log per condition and `concurrent_vi_matching.png` (relative responses against relative reinforcement, with the diagonal), and prints the counts for each condition and the fit of the generalized matching law. The end of the output:

```
  "sensitivity": 0.941,
  "bias": -0.09,
  "r_squared": 0.953,
  "max_deviation": 0.057
}
```

The run took about 20 s. The subject is a model written for this example, so the fit shows that the schedules, the changeover delay, the logging, and the analysis work together; it is not evidence about animals.

## Examples

| Example | Experiment | Schedule |
|---|---|---|
| [fi_scallop](examples/fi_scallop/README.md) | Fixed-interval scallop: a pause after each reinforcer, then accelerating responding (Ferster & Skinner, 1957) | `FI 60-s` |
| [concurrent_vi_matching](examples/concurrent_vi_matching/README.md) | Relative responses track relative reinforcement (Herrnstein, 1961) | `Conc(VI 180-s, VI 180-s, COD=1.5-s)` and three more pairs |
| [drl_irt](examples/drl_irt/README.md) | Differential reinforcement of low rate: inter-response times lengthen and the rate falls (Ferster & Skinner, 1957) | `DRL 10-s` |
| [paper_procedure](examples/paper_procedure/README.md) | A published procedure run from its DOI and judged against the paper's qualitative pattern | extracted from the paper's Method section |

Each example writes its logs and figures next to its `run.py`. See [examples/README.md](examples/README.md) for details. `tests/test_examples.py` runs every example and checks its pattern, and `tests/laws/` compares simulated FI, concurrent VI VI, and ratio-versus-interval responding with values reported in the original papers (cited in each test file).

## What gets installed

| Package | Import name | Role |
|---|---|---|
| [contingency-dsl-py](https://github.com/OperantKit/contingency-dsl-py) | `contingency_dsl` | Parser for the contingency-dsl schedule language |
| [contingency-py](https://github.com/OperantKit/contingency-py) | `contingency` | Reinforcement schedule engine |
| [experiment-core](https://github.com/OperantKit/experiment-core) | `experiment_core` | Session lifecycle, experiment context, renewal designs |
| [session-runner](https://github.com/OperantKit/session-runner) | `session_runner` | Drives a session and passes its events on |
| [session-recorder](https://github.com/OperantKit/session-recorder) | `session_recorder` | Writes and reads OKL event logs |
| [session-analyzer](https://github.com/OperantKit/session-analyzer) | `session_analyzer` | Cumulative records, statistics, model fitting |
| [experiment-io](https://github.com/OperantKit/experiment-io) | `experiment_io` | Device input and output: virtual, serial-port, and hardware-in-the-loop backends |
| [operantkit-cli](https://github.com/OperantKit/operantkit-cli) | `operantkit_cli` | The `operant run` command |

Not included: the Method-section tools ([contingency-dsl2procedure](https://github.com/OperantKit/contingency-dsl2procedure), [contingency-procedure2dsl](https://github.com/OperantKit/contingency-procedure2dsl)), the assistant integration ([operantkit-mcp](https://github.com/OperantKit/operantkit-mcp)), and the authoring and display tools such as [schedule-writer](https://github.com/OperantKit/schedule-writer) and [session-visualizer](https://github.com/OperantKit/session-visualizer). Install those separately.

## Limitations

- **Not on PyPI yet.** Until the release, use the `--no-deps` installation above.
- **The subjects are models.** Each example's subject was written to produce the pattern of its experiment. The examples show that OperantKit delivers the contingency as written; they do not predict what your animals will do.

## References

Ferster, C. B., & Skinner, B. F. (1957). *Schedules of reinforcement*. Appleton-Century-Crofts. https://doi.org/10.1037/10627-000

Herrnstein, R. J. (1961). Relative and absolute strength of response as a function of frequency of reinforcement. *Journal of the Experimental Analysis of Behavior*, *4*(3), 267–272. https://doi.org/10.1901/jeab.1961.4-267

## License

MIT. See [LICENSE](LICENSE).

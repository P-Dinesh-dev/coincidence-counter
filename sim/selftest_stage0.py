"""Gate 0: does the simulator reproduce the textbook dead-time curves?

Both models have a known closed form for the measured rate m given the true
rate n:

    non-paralyzable     m = n / (1 + n*tau)        saturates at 1/tau
    paralyzable         m = n * exp(-n*tau)        peaks, then collapses

We sweep n across the interesting range, simulate, and check the simulation
lands on those curves.  If it does not, the simulator is wrong -- not the
textbook -- and nothing built on top of it would mean anything.

Run from the repo root:   python -m sim.selftest_stage0
"""

import numpy as np
import matplotlib.pyplot as plt

from sim.generator import poisson_events
from sim.deadtime import paralyzable, non_paralyzable

TAU = 100e-6            # 100 us, typical of a Geiger-Muller tube
EVENTS_PER_POINT = 200_000
SEED = 20260917


def analytic_non_paralyzable(n, tau):
    return n / (1 + n * tau)


def analytic_paralyzable(n, tau):
    return n * np.exp(-n * tau)


def run_sweep():
    """Simulate both models across the sweep and return measured rates."""
    # n*tau spans 0.01 to ~3: comfortably through the paralyzable turnover at
    # n*tau = 1, but stopping before the measured rate collapses so far that
    # too few events survive to say anything useful about it.
    true_rates = np.logspace(2, 4.5, 18)
    rng = np.random.default_rng(SEED)

    measured = {"non_paralyzable": [], "paralyzable": []}

    for n in true_rates:
        # Fixed event count rather than fixed duration, so every point on the
        # sweep carries the same statistical precision.
        duration = EVENTS_PER_POINT / n
        arrivals = poisson_events(n, duration, rng)

        measured["non_paralyzable"].append(len(non_paralyzable(arrivals, TAU)) / duration)
        measured["paralyzable"].append(len(paralyzable(arrivals, TAU)) / duration)

    return true_rates, {k: np.array(v) for k, v in measured.items()}


def residuals_in_sigma(measured_rate, expected_rate, duration):
    """How far off we are, counted in standard deviations.

    The scale used here is sqrt(N) on the surviving counts.  That is the
    Poisson width, and it is deliberately conservative: dead time makes the
    counts *more* regular than Poisson, so the true spread is narrower.  We
    measure that suppression properly in Stage 1 via the Fano factor.
    """
    expected_counts = expected_rate * duration
    return (measured_rate - expected_rate) * duration / np.sqrt(expected_counts)


def main():
    true_rates, measured = run_sweep()
    durations = EVENTS_PER_POINT / true_rates

    expected = {
        "non_paralyzable": analytic_non_paralyzable(true_rates, TAU),
        "paralyzable": analytic_paralyzable(true_rates, TAU),
    }

    print(f"Gate 0 self-test   tau = {TAU * 1e6:.0f} us, "
          f"{EVENTS_PER_POINT:,} events per point\n")

    worst = 0.0
    for model in ("non_paralyzable", "paralyzable"):
        sigma = residuals_in_sigma(measured[model], expected[model], durations)
        worst = max(worst, np.abs(sigma).max())
        print(f"  {model:18s} max deviation {np.abs(sigma).max():5.2f} sigma")

    passed = worst < 3.0
    print(f"\n  {'PASS' if passed else 'FAIL'} -- worst case {worst:.2f} sigma "
          f"against a 3 sigma threshold")

    plot(true_rates, measured, expected)
    return passed


def plot(true_rates, measured, expected):
    fig, ax = plt.subplots(figsize=(7, 5))

    # The line a counter would follow if it never missed anything.
    ax.plot(true_rates, true_rates, ":", color="grey", label="ideal (no dead time)")

    for model, colour in (("non_paralyzable", "tab:blue"), ("paralyzable", "tab:red")):
        ax.plot(true_rates, expected[model], "-", color=colour,
                label=f"{model.replace('_', '-')} (theory)")
        ax.plot(true_rates, measured[model], "o", color=colour,
                markersize=4, label=f"{model.replace('_', '-')} (simulated)")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("true rate n  (events/s)")
    ax.set_ylabel("measured rate m  (events/s)")
    ax.set_title(f"Dead-time loss, tau = {TAU * 1e6:.0f} us   [simulated]")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")

    fig.tight_layout()
    fig.savefig("figures/stage0_deadtime_curves.png", dpi=150)
    print("\n  wrote figures/stage0_deadtime_curves.png")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

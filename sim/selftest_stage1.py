"""Gate 1: do the four tau methods agree, and can we break the degeneracy?

Two things get checked here.

First, we hide a known tau inside simulated data and see whether four methods
that lean on different physics can each find it.  Agreement is what licenses
us to trust tau when it is genuinely unknown.

Second, the Lambert-W degeneracy.  We take one measured rate, show it has two
perfectly good true rates behind it, and then resolve which is real by
nudging the source -- the observation that costs nothing and settles it.

Run from the repo root:   python -m sim.selftest_stage1
"""

import numpy as np
import matplotlib.pyplot as plt

from sim.generator import poisson_events
from sim.deadtime import non_paralyzable, paralyzable
from sim.estimators import (invert_non_paralyzable, invert_paralyzable,
                            branch_from_perturbation, LOW_RATE_BRANCH,
                            HIGH_RATE_BRANCH, relative_error_gain_non_paralyzable)
from sim.tau_methods import (tau_from_two_sources, tau_from_intervals,
                             tau_from_fano, tau_from_pulser)

TAU = 100e-6
SEED = 20260917
TOLERANCE = 0.10        # every method must land within 10% of the truth


def measure(rate, duration, rng):
    """Measured rate and arrival times for a non-paralyzable counter."""
    survived = non_paralyzable(poisson_events(rate, duration, rng), TAU)
    return len(survived) / duration, survived


def check_four_methods(rng):
    """Recover TAU four ways from data that never mentions it."""
    estimates = {}

    # A -- two sources. Rates add truthfully; measured rates do not.
    m1, _ = measure(1500, 200, rng)
    m2, _ = measure(2500, 200, rng)
    m12, _ = measure(4000, 200, rng)
    estimates["two-source"] = tau_from_two_sources(m1, m2, m12, invert_non_paralyzable)

    # B -- the smallest gap that ever appears in a long record.
    _, times = measure(2000, 400, rng)
    estimates["intervals"], _ = tau_from_intervals(times)

    # C -- how far the counts fall below Poisson scatter. Needs many bins,
    # each holding many events, so this run is deliberately the longest.
    duration = 1000
    _, times = measure(2000, duration, rng)
    estimates["fano"], fano = tau_from_fano(times, duration, bin_width=0.2)

    # D -- rates we chose ourselves, which is what the FPGA pulser will do.
    known = np.array([500, 1000, 2000, 4000, 8000])
    seen = np.array([measure(n, 100, rng)[0] for n in known])
    estimates["pulser"], pulser_err = tau_from_pulser(known, seen, "non_paralyzable")

    print(f"Gate 1   true tau = {TAU * 1e6:.1f} us (hidden from every method)\n")
    for name, tau in estimates.items():
        deviation = (tau - TAU) / TAU
        flag = "ok" if abs(deviation) < TOLERANCE else "OUT"
        print(f"  {name:12s} {tau * 1e6:7.2f} us   {deviation:+6.1%}   {flag}")

    print(f"\n  (fano factor measured {fano:.4f}, expected "
          f"{(1 - 2000 / (1 + 2000 * TAU) * TAU) ** 2:.4f};"
          f" pulser s.e. {pulser_err * 1e6:.2f} us)")

    return all(abs(t - TAU) / TAU < TOLERANCE for t in estimates.values())


def check_degeneracy(rng):
    """Show one measured rate hiding two true rates, then resolve it."""
    # Pick a true rate below the peak at n = 1/tau, work out what it measures,
    # then ask Lambert W for the other rate that measures the same.
    #
    # There is no elementary rearrangement for that second rate -- taking logs
    # of m = n*exp(-n*tau) leaves ln(n) and n on the same side. Lambert W is
    # not decoration here, it is the only closed form there is.
    low_true = 2000.0
    ambiguous_m = low_true * np.exp(-low_true * TAU)

    from_low = invert_paralyzable(ambiguous_m, TAU, LOW_RATE_BRANCH)
    from_high = invert_paralyzable(ambiguous_m, TAU, HIGH_RATE_BRANCH)
    high_true = float(from_high)

    print(f"\n  One measured rate, two honest answers:")
    print(f"    measured            {ambiguous_m:9.1f} /s")
    print(f"    low-rate branch     {from_low:9.1f} /s")
    print(f"    high-rate branch    {from_high:9.1f} /s")
    print(f"    ratio               {from_high / from_low:9.1f}x apart")

    # Now break it. Raise the true rate 5% and watch which way the needle
    # moves: up means we were below the peak, down means above it.
    resolved = {}
    for label, n in (("low", low_true), ("high", high_true)):
        before = len(paralyzable(poisson_events(n, 40, rng), TAU)) / 40
        after = len(paralyzable(poisson_events(n * 1.05, 40, rng), TAU)) / 40
        branch = branch_from_perturbation(before, after)
        expected = LOW_RATE_BRANCH if label == "low" else HIGH_RATE_BRANCH
        resolved[label] = branch == expected
        print(f"    nudging the {label:4s} case: {before:7.1f} -> {after:7.1f} /s"
              f"  => {'low' if branch == LOW_RATE_BRANCH else 'high'} branch"
              f"  {'ok' if resolved[label] else 'WRONG'}")

    return all(resolved.values()), low_true, high_true, ambiguous_m


def plot_degeneracy(low_true, high_true, ambiguous_m):
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5))

    n = np.logspace(2, np.log10(4 / TAU), 400)
    left.plot(n, n * np.exp(-n * TAU), color="tab:red")
    left.axhline(ambiguous_m, color="grey", ls="--", lw=1)
    left.plot([low_true, high_true], [ambiguous_m, ambiguous_m], "ko", markersize=7)
    left.annotate("one reading", (n[0] * 1.2, ambiguous_m * 1.15), fontsize=9, color="grey")
    left.annotate("two true rates", (low_true * 1.3, ambiguous_m * 0.55), fontsize=9)
    left.set_xscale("log")
    left.set_xlabel("true rate n  (events/s)")
    left.set_ylabel("measured rate m  (events/s)")
    left.set_title("Paralyzable degeneracy   [simulated]")
    left.grid(alpha=0.3, which="both")

    # How much the correction costs you in precision, non-paralyzable case.
    m = np.linspace(1, 0.95 / TAU, 400)
    right.plot(m * TAU, relative_error_gain_non_paralyzable(m, TAU), color="tab:blue")
    right.axhline(2, color="grey", ls=":", lw=1)
    right.annotate("error doubles at 50% loss", (0.06, 2.25), fontsize=9, color="grey")
    right.set_xlabel("fraction of time dead,  m*tau")
    right.set_ylabel("fractional error multiplier")
    right.set_title("What the correction costs   [simulated]")
    right.set_ylim(0, 12)
    right.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig("figures/stage1_degeneracy_and_error.png", dpi=150)
    print("\n  wrote figures/stage1_degeneracy_and_error.png")


def main():
    rng = np.random.default_rng(SEED)

    methods_agree = check_four_methods(rng)
    branch_resolved, low, high, m = check_degeneracy(rng)

    plot_degeneracy(low, high, m)

    passed = methods_agree and branch_resolved
    print(f"\n  {'PASS' if passed else 'FAIL'} -- "
          f"four methods {'agree' if methods_agree else 'DISAGREE'}, "
          f"degeneracy {'resolved' if branch_resolved else 'UNRESOLVED'}")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

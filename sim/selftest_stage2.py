"""Gate 2a: does the coincidence logic obey the accidental-rate prediction?

Coincidence gating throws away uncorrelated noise, but not all of it -- two
unrelated pulses will sometimes land in the same window by chance.  Theory
says that accidental rate is 2*tau*R1*R2: linear in the window and through the
origin.  That is a real prediction, made in advance, with a shape that can
fail.

We feed the logic two Poisson streams that share no particles at all, so every
coincidence it reports is by construction accidental, and sweep the window.

Two quantities get compared, and the distinction matters:

  pairs   how many (a, b) pulses fall within the window of each other.  This
          is what 2*tau*R1*R2 actually counts, and it is what we gate on.

  asserts how many clock cycles the RTL raised `coincident`.  At most one per
          cycle however many partners were in range, so it sits slightly below
          the pair count, by more as the window widens.  We check it lands
          where that reasoning says it should.

Run from the repo root:   python -m sim.selftest_stage2
"""

import numpy as np
import matplotlib.pyplot as plt

from sim.generator import poisson_events
from sim.rtl_model import (to_cycles, count_coincidences, count_pairs,
                           accidental_pair_rate)

CLK_HZ = 100e6          # 100 MHz -> 10 ns per cycle
NOMINAL_RATE = 10_000.0
DURATION = 60.0
WINDOWS = [10, 20, 50, 100, 200, 300, 500]      # clock cycles
SEED = 20260917
SIGMA_LIMIT = 3.0


def main():
    rng = np.random.default_rng(SEED)

    a = to_cycles(poisson_events(NOMINAL_RATE, DURATION, rng), CLK_HZ)
    b = to_cycles(poisson_events(NOMINAL_RATE, DURATION, rng), CLK_HZ)

    # The formula takes the rates the counter actually saw, not the rates we
    # asked for. Those differ by a fraction of a percent from Poisson scatter
    # alone, which is larger than the effect we are trying to measure.
    rate_a, rate_b = len(a) / DURATION, len(b) / DURATION

    print(f"Gate 2a   {CLK_HZ / 1e6:.0f} MHz clock, {DURATION:.0f} s")
    print(f"  measured singles  R1 = {rate_a:.1f}/s   R2 = {rate_b:.1f}/s\n")
    print(f"  {'window':>7} {'pairs':>9} {'2*t*R1*R2':>10} {'dev':>7}   "
          f"{'asserts':>9} {'/pairs':>8} {'floor':>7}")
    print(f"  {'cycles':>7} {'/s':>9} {'/s':>10} {'sigma':>7}   {'/s':>9}")

    worst_sigma, assert_ok = 0.0, True
    pair_rates, assert_rates = [], []

    for window in WINDOWS:
        pairs = count_pairs(a, b, window)
        asserts = count_coincidences(a, b, window)
        predicted = accidental_pair_rate(rate_a, rate_b, window, CLK_HZ)

        # Accidentals are themselves a Poisson count, so sqrt(N) is the right
        # scale here -- unlike Stage 0, nothing is suppressing the variance.
        sigma = (pairs / DURATION - predicted) / (np.sqrt(pairs) / DURATION)
        worst_sigma = max(worst_sigma, abs(sigma))

        # The assert count cannot exceed the pair count, and cannot fall below
        # the case where each pulse yields at most one assert.
        x = 2 * ((window + 0.5) / CLK_HZ) * rate_b
        floor = (1 - np.exp(-x)) / x
        ratio = asserts / pairs
        assert_ok &= floor - 0.01 <= ratio <= 1.001

        pair_rates.append(pairs / DURATION)
        assert_rates.append(asserts / DURATION)

        print(f"  {window:7d} {pairs / DURATION:9.1f} {predicted:10.1f} "
              f"{sigma:+7.2f}   {asserts / DURATION:9.1f} {ratio:8.4f} {floor:7.4f}")

    plot(np.array(WINDOWS, float), pair_rates, assert_rates, rate_a, rate_b)

    pairs_ok = worst_sigma < SIGMA_LIMIT
    passed = pairs_ok and assert_ok
    print(f"\n  pairs vs prediction: worst {worst_sigma:.2f} sigma "
          f"against {SIGMA_LIMIT:.0f} -- {'ok' if pairs_ok else 'OUT'}")
    print(f"  asserts within [saturation floor, pairs] -- "
          f"{'ok' if assert_ok else 'OUT'}")
    print(f"\n  {'PASS' if passed else 'FAIL'}")
    return passed


def plot(windows, pair_rates, assert_rates, rate_a, rate_b):
    fig, ax = plt.subplots(figsize=(7, 5))

    fine = np.linspace(0, windows.max() * 1.05, 200)
    ax.plot(fine, accidental_pair_rate(rate_a, rate_b, fine, CLK_HZ),
            "-", color="tab:green", label="2*tau*R1*R2  (predicted in advance)")
    ax.plot(windows, pair_rates, "o", color="tab:purple", markersize=6,
            label="pulse pairs in window (measured)")
    ax.plot(windows, assert_rates, "s", color="tab:orange", markersize=5,
            markerfacecolor="none", label="RTL coincidence asserts (measured)")

    ax.set_xlabel("coincidence window  (clock cycles)")
    ax.set_ylabel("accidental coincidence rate  (/s)")
    ax.set_title(f"Accidentals from two unrelated sources, "
                 f"{rate_a / 1000:.1f} kHz each   [simulated]")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    fig.savefig("figures/stage2_accidentals.png", dpi=150)
    print("\n  wrote figures/stage2_accidentals.png")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

"""Stage 4: run the pipeline over data we did not generate.

Everything before this was checked against simulations we wrote ourselves,
which can only confirm that our algebra is self-consistent.  This stage uses
62.8 hours of real cosmic-ray muon data recorded by a CosmicWatch v3X
detector (see ATTRIBUTION.md), and it is the first thing here that can tell us
something we did not put in.

The recording is unusually good for the purpose: the detector logged its own
accumulated dead time alongside every event, so there is an independent
number to check our estimators against rather than one we chose.

It turned out to disagree with them, and the disagreement is the result.

Run from the repo root:   python -m sim.validate_stage4
"""

import pathlib

import numpy as np
import matplotlib.pyplot as plt

from sim.estimators import invert_non_paralyzable
from sim.tau_methods import tau_from_intervals, tau_from_fano

DATA = pathlib.Path("validation/AxLab_C_001.txt")
CACHE = pathlib.Path("data/cosmicwatch.npy")


def load():
    """Timestamps, coincidence flags, pulse heights, cumulative dead time.

    Cached as .npy because parsing 688k lines of text takes long enough to
    discourage re-running the analysis, and an analysis you avoid re-running
    is one you stop checking.
    """
    if CACHE.exists():
        return np.load(CACHE)

    CACHE.parent.mkdir(exist_ok=True)
    # Columns: event, timestamp[s], flag, adc, sipm[mV], deadtime[s], ...
    raw = np.genfromtxt(DATA, comments="#", usecols=(1, 2, 3, 5), dtype=float)
    np.save(CACHE, raw)
    return raw


def main():
    times, flags, adc, cumulative_dead = load().T

    duration = times[-1] - times[0]
    n_events = len(times)
    raw_rate = n_events / duration

    gaps = np.diff(times)
    reported_dead = np.diff(cumulative_dead)
    total_dead = cumulative_dead[-1] - cumulative_dead[0]

    print(f"Stage 4   CosmicWatch v3X, {DATA.name}\n")
    print(f"  events        {n_events:,}")
    print(f"  duration      {duration:,.0f} s  ({duration / 3600:.1f} h)")
    print(f"  raw rate      {raw_rate:.4f} /s")
    print(f"  coincident    {int(flags.sum()):,} ({100 * flags.mean():.1f}%)")
    print(f"  m*tau         {raw_rate * reported_dead.mean():.5f}  "
          f"-- this detector is almost never busy")

    print(f"\n  the detector's own dead-time accounting")
    print(f"    total       {total_dead:.1f} s ({100 * total_dead / duration:.3f}% of run)")
    print(f"    per event   mean {reported_dead.mean() * 1e6:.1f} us, "
          f"sd {reported_dead.std() * 1e6:.1f} us, "
          f"range {reported_dead.min() * 1e6:.0f}-{reported_dead.max() * 1e6:.0f} us")

    # ------------------------------------------------------------------
    # Cross-check: the live-time correction and our inversion are the same
    # formula.  N/(T - N*tau) == m/(1 - m*tau) with m = N/T.  The detector's
    # authors and this project reached it from opposite directions.
    # ------------------------------------------------------------------
    live_time_rate = n_events / (duration - total_dead)
    ours = float(invert_non_paralyzable(raw_rate, reported_dead.mean()))

    print(f"\n  corrected rate")
    print(f"    raw                {raw_rate:.5f} /s")
    print(f"    live-time method   {live_time_rate:.5f} /s")
    print(f"    our inversion      {ours:.5f} /s   "
          f"(agree to {abs(ours - live_time_rate) / live_time_rate:.0e})")

    # ------------------------------------------------------------------
    # The finding.  Slack is the time between an event's dead period ending
    # and the next event arriving.  If the reported dead time were the whole
    # story, slack would be exponential with mean 1/rate, and its minimum over
    # 688k samples would sit a fraction of a microsecond above zero.
    # ------------------------------------------------------------------
    slack = gaps - reported_dead
    expected_min = 1 / (n_events * raw_rate)
    # P(no slack below the observed floor | purely exponential waiting)
    log_p = -n_events * raw_rate * slack.min()

    print(f"\n  unreported dead time")
    print(f"    shortest gap ever seen        {gaps.min() * 1e6:7.1f} us")
    print(f"    shortest slack                {slack.min() * 1e6:7.1f} us")
    print(f"    expected if only reported     {expected_min * 1e6:7.2f} us")
    print(f"    negative slack (bookkeeping)  {int((slack < 0).sum())}")
    print(f"\n    Across {n_events:,} events not one arrived sooner than")
    print(f"    {slack.min() * 1e6:.0f} us after the reported dead time ended. If that")
    print(f"    were chance, its probability is exp({log_p:.0f}) ~ 1e{log_p / np.log(10):.0f}.")
    print(f"    So the detector blocks for about {slack.min() * 1e6:.0f} us longer than it")
    print(f"    reports -- roughly {100 * slack.min() / reported_dead.mean():.0f}% beyond its own figure.")

    effective_tau = reported_dead.mean() + slack.min()

    # ------------------------------------------------------------------
    # Our estimators, given only timestamps, against both candidate truths.
    # ------------------------------------------------------------------
    tau_b, _ = tau_from_intervals(times)
    tau_c, fano, tau_c_error = tau_from_fano(times, duration, bin_width=600.0)

    print(f"\n  our estimators, given only the timestamps")
    print(f"    {'':22s} {'value':>12} {'vs reported':>12} {'vs effective':>13}")
    print(f"    {'reported (detector)':22s} {reported_dead.mean() * 1e6:9.1f} us")
    print(f"    {'effective (rep+slack)':22s} {effective_tau * 1e6:9.1f} us")
    print(f"    {'intervals (B)':22s} {tau_b * 1e6:9.1f} us "
          f"{(tau_b - reported_dead.mean()) / reported_dead.mean():+11.1%} "
          f"{(tau_b - effective_tau) / effective_tau:+12.1%}")
    print(f"    {'fano (C)':22s} {tau_c * 1e6:9.1f} us "
          f"+/- {tau_c_error * 1e6:,.0f} us")

    print(f"\n    Method B lands within "
          f"{abs(tau_b - effective_tau) / effective_tau:.1%} of the effective dead time")
    print(f"    while sitting {(tau_b - reported_dead.mean()) / reported_dead.mean():+.0%} off the reported one. It is not wrong;")
    print(f"    it is measuring the blocking that actually happened.")
    print(f"\n    Method C is useless here, and says so: its error bar is")
    print(f"    +/-{tau_c_error * 1e6:,.0f} us on a {tau_c * 1e6:.0f} us answer, {tau_c_error / tau_c:,.0f}x the quantity")
    print(f"    being measured. At m*tau = {raw_rate * effective_tau:.4f} the variance suppression")
    print(f"    it relies on (F = {fano:.4f}) is far smaller than the scatter of F")
    print(f"    itself. Its apparent agreement in the table is coincidence.")

    plot(reported_dead, slack, gaps, effective_tau, raw_rate, tau_b)
    return True


def plot(reported_dead, slack, gaps, effective_tau, raw_rate, tau_b):
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Slack is what is left of the gap once the detector's own dead time is
    # subtracted. If nothing else blocked the counter, this is the waiting
    # time for the next muon: exponential, and therefore populated all the way
    # down to zero. Log bins, because the interesting part spans microseconds
    # to seconds.
    bins = np.logspace(0, 7, 90)                       # 1 us to 10 s
    left.hist(slack * 1e6, bins=bins, color="tab:blue", alpha=0.8,
              label="observed slack")

    # What a pure exponential would have put in each of those bins.
    rate = 1 / slack.mean()
    expected = len(slack) * (np.exp(-rate * bins[:-1] * 1e-6)
                             - np.exp(-rate * bins[1:] * 1e-6))
    left.step(bins[:-1], expected, where="post", color="tab:red", lw=1.3,
              label="exponential waiting (expected)")

    left.axvline(slack.min() * 1e6, color="black", ls="--", lw=1.3,
                 label=f"hard floor {slack.min() * 1e6:.0f} us")
    left.set_xscale("log")
    left.set_yscale("log")
    left.set_xlabel("slack = gap - reported dead time   (us)")
    left.set_ylabel("events")
    left.set_title("Blocking the detector never reports   [hardware]")
    left.legend(fontsize=7, loc="upper left")
    left.grid(alpha=0.3, which="both")

    rates = np.logspace(0, np.log10(0.9 / effective_tau), 300)
    right.plot(rates, invert_non_paralyzable(rates, effective_tau) / rates,
               color="tab:green")
    right.axvline(raw_rate, color="grey", ls="--", lw=1.2)
    right.annotate(f"this run: {raw_rate:.2f}/s\ncorrection "
                   f"+{100 * (1 / (1 - raw_rate * effective_tau) - 1):.2f}%",
                   (raw_rate * 1.5, 3.2), fontsize=8, color="grey")
    right.set_xscale("log")
    right.set_xlabel("measured rate  (/s)")
    right.set_ylabel("correction factor  n/m")
    right.set_title(f"Correction vs rate, tau = {effective_tau * 1e6:.0f} us   [hardware]")
    right.set_ylim(0.9, 11)
    right.grid(alpha=0.3, which="both")

    fig.tight_layout()
    fig.savefig("figures/stage4_real_data.png", dpi=150)
    print("\n  wrote figures/stage4_real_data.png")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

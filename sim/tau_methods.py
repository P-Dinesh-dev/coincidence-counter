"""Four independent ways to measure the dead time.

Most projects read tau off a datasheet and move on.  A datasheet number is a
typical value for a part family at some temperature, not a measurement of the
counter sitting in front of you, and the whole correction hangs off it.

So we measure it four ways that lean on different physics, and check they
agree.  If they do, tau is real.  If they do not, that disagreement is a
finding about the instrument and belongs in the write-up.
"""

import numpy as np
from scipy.optimize import brentq


def tau_from_two_sources(m1, m2, m12, invert):
    """Method A -- two sources, no calibration needed.

    True rates add: a source producing n1 and one producing n2 together
    produce n1 + n2, exactly.  Measured rates do not add, because the counter
    is busier when both are present.  The tau that reconciles the two is the
    tau of the counter.

    We solve that numerically rather than quoting a closed form, so the same
    function works for whichever inversion you hand it.
    """
    def mismatch(tau):
        return invert(m12, tau) - (invert(m1, tau) + invert(m2, tau))

    # Below the ceiling of the busiest measurement, since every inversion here
    # must stay physical.  Both models go singular at or before 1/m12.
    return brentq(mismatch, 1e-12, 0.999 / m12)


def tau_from_intervals(measured_times):
    """Method B -- the gap that never appears.

    With non-paralyzable dead time an accepted event waits tau and then waits
    an exponential time for the next particle, so observed gaps are an
    exponential shifted bodily to the right by tau.  For that distribution the
    maximum-likelihood estimate of the shift is simply the smallest gap seen,
    and the rate follows from the mean of what is left.

    Slightly biased high -- the smallest gap in a finite sample sits just
    above tau, never below -- and the bias shrinks as events accumulate.
    """
    gaps = np.diff(measured_times)
    tau = gaps.min()
    return tau, 1 / (gaps.mean() - tau)


def tau_from_fano(measured_times, duration, bin_width):
    """Method C -- dead time makes the counts too regular.

    Pure random arrivals give variance equal to mean, a Fano factor of 1.
    Dead time forbids close pairs, which shaves the tail off the count
    distribution and pushes the Fano factor below 1.  For non-paralyzable
    dead time over long bins that suppression works out to F = (1 - m*tau)^2
    (derivation in SPEC.md), which rearranges to tau directly.

    Needs bins long compared with the mean gap for the asymptotic form to
    hold; the caller chooses bin_width and is responsible for that.
    """
    counts, _ = np.histogram(measured_times, bins=np.arange(0, duration, bin_width))
    fano = counts.var() / counts.mean()
    measured_rate = len(measured_times) / duration

    return (1 - np.sqrt(fano)) / measured_rate, fano


def tau_from_pulser(true_rates, measured_rates, model):
    """Method D -- feed in a rate you already know.

    Both models rearrange to give tau in closed form per point, with no
    fitting at all:

        non-paralyzable   1/m = 1/n + tau      ->  tau = 1/m - 1/n
        paralyzable       ln(n/m) = n*tau      ->  tau = ln(n/m)/n

    This is the method that needs no radioactive source, only a generator
    whose rate you set yourself -- which is why the FPGA carries one.
    """
    true_rates, measured_rates = np.asarray(true_rates), np.asarray(measured_rates)

    if model == "non_paralyzable":
        per_point = 1 / measured_rates - 1 / true_rates
    elif model == "paralyzable":
        per_point = np.log(true_rates / measured_rates) / true_rates
    else:
        raise ValueError(f"unknown model {model!r}")

    return per_point.mean(), per_point.std(ddof=1) / np.sqrt(len(per_point))

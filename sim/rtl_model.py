"""A cycle-faithful replay of what rtl/coincidence.v does.

This is not a second design.  It is the same logic written where we can reason
about it, so that two things become possible: we can test the coincidence
scheme today without a Verilog simulator, and once we have one we can demand
that the Verilog agree with this model event for event rather than merely
"look about right".

It steps only the cycles on which something happens.  Stepping all of them
would be 100 million iterations per second of simulated time and would tell us
nothing extra, since the state only changes when a pulse arrives.
"""

import numpy as np


def to_cycles(times, clk_hz):
    """Arrival times in seconds -> the clock cycle each one lands in.

    Two particles inside the same cycle become one pulse, exactly as they
    would in the FPGA: the edge detector emits one pulse per rising edge and
    cannot resolve anything finer than its own clock.  That is a real dead
    time of one clock period, and it belongs in the model.
    """
    return np.unique(np.floor(np.asarray(times) * clk_hz).astype(np.int64))


def count_coincidences(a_cycles, b_cycles, window):
    """Number of cycles on which coincidence.v would assert `coincident`.

    Mirrors the RTL exactly: each channel stays flagged from its pulse cycle
    until `window` cycles have elapsed, and a coincidence is declared when a
    pulse lands while the other channel is still flagged.
    """
    a_set, b_set = set(a_cycles.tolist()), set(b_cycles.tolist())
    last_a = last_b = None
    total = 0

    for cycle in sorted(a_set | b_set):
        a_pulse, b_pulse = cycle in a_set, cycle in b_set

        # Trace the RTL carefully. `a_left` is a register, so a pulse at cycle
        # c makes it `window` at c+1, and it decrements from there: at c+k it
        # holds window-(k-1), which stays above zero while k <= window. So the
        # flag reaches exactly `window` cycles past the pulse, not window-1.
        # Getting this boundary wrong understates coincidences by 2/(2w+1),
        # which is 10% at w=10 -- small in cycles, large in results.
        a_recent = a_pulse or (last_a is not None and cycle - last_a <= window)
        b_recent = b_pulse or (last_b is not None and cycle - last_b <= window)

        if (a_pulse and b_recent) or (b_pulse and a_recent):
            total += 1

        if a_pulse:
            last_a = cycle
        if b_pulse:
            last_b = cycle

    return total


def accidental_rate(rate_a, rate_b, window_seconds):
    """The coincidence rate you get from two sources that share no particles.

    Each pulse on A opens a window of +/- tau around itself, so B has 2*tau
    of opportunity per A pulse to land inside by pure chance.  Valid while the
    accidental rate stays well below the singles rates, which is the regime
    any sane coincidence setup operates in.
    """
    return 2 * window_seconds * rate_a * rate_b


def count_pairs(a_cycles, b_cycles, window):
    """Number of (a, b) pulse pairs closer together than `window` cycles.

    This is what the 2*tau*R1*R2 formula actually counts -- pairs.  The RTL
    counts something subtly different: *cycles on which a coincidence was
    declared*, which is at most one per cycle no matter how many partners
    were in range.  Comparing the two is how we find out how much that
    distinction costs.
    """
    # Each a pulse admits every b within [a - window, a + window], so the
    # count is just the gap between two binary searches into the sorted b.
    lo = np.searchsorted(b_cycles, a_cycles - window, side="left")
    hi = np.searchsorted(b_cycles, a_cycles + window, side="right")
    return int((hi - lo).sum())


def accidental_pair_rate(rate_a, rate_b, window_cycles, clk_hz):
    """Expected accidental *pair* rate, with the discrete window written out.

    A window of `w` cycles reaching both ways admits 2w+1 distinct cycle
    offsets, not 2w -- the pulse's own cycle counts once, not twice.  So the
    effective tau is (w + 0.5) clock periods.
    """
    return 2 * ((window_cycles + 0.5) / clk_hz) * rate_a * rate_b

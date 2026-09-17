"""Generation of ideal (dead-time-free) particle arrival times.

Radioactive decay is memoryless: the chance a nucleus decays in the next
microsecond does not depend on how long you have already been waiting.  The
arrival times of such events form a Poisson process, and the *gaps* between
consecutive arrivals are exponentially distributed with mean 1/rate.

That gap distribution is all we need -- draw the gaps, add them up, and the
running total is the arrival time of each particle.
"""

import numpy as np


def poisson_events(rate, duration, rng):
    """Return sorted arrival times (in seconds) of a Poisson process.

    `rate` is in events per second, `duration` in seconds.  `rng` is a
    numpy Generator, passed in rather than created here so that every
    experiment in this project can be re-run with an identical seed.
    """
    # Draw comfortably more gaps than we expect to need.  The event count is
    # itself random (mean rate*duration, spread ~sqrt of that), so 20% headroom
    # plus a floor of 1000 leaves the shortfall astronomically unlikely.
    n_draw = int(rate * duration * 1.2) + 1000

    times = np.cumsum(rng.exponential(1.0 / rate, n_draw))

    # If this trips, the headroom above was not enough and we would have
    # silently undercounted -- which would quietly corrupt every rate we
    # measure later.  Better to fail loudly.
    assert times[-1] > duration, "ran out of events before the run ended"

    return times[times < duration]

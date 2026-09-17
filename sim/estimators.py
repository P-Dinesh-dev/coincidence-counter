"""Recovering the true rate from the measured one, and how badly that can go.

Stage 0 went forwards: true rate -> measured rate.  This goes backwards, which
is the direction a real instrument has to work in, and it is much less
comfortable.

Non-paralyzable inverts cleanly.  Paralyzable does not: its curve rises to a
peak at n = 1/tau and falls again, so a single measured rate is consistent
with *two* true rates -- one either side of the peak.  No amount of staring at
that one number will tell you which.  You need a second observation, and
`branch_from_perturbation` below is the cheapest honest one.
"""

import numpy as np
from scipy.special import lambertw

LOW_RATE_BRANCH = 0     # before the peak, n*tau < 1
HIGH_RATE_BRANCH = -1   # after the peak, n*tau > 1


def invert_non_paralyzable(m, tau):
    """True rate from measured rate.  Returns nan above the 1/tau ceiling."""
    # m*tau = 1 is the saturation ceiling: the model cannot produce a measured
    # rate at or above 1/tau, so anything there is unphysical rather than just
    # noisy, and must not be quietly turned into a huge finite number.
    return np.where(m * tau < 1, m / (1 - m * tau), np.nan)


def invert_paralyzable(m, tau, branch=LOW_RATE_BRANCH):
    """True rate from measured rate, on the branch you ask for.

    From m = n*exp(-n*tau), substituting u = -n*tau gives u*exp(u) = -m*tau,
    which is exactly the equation Lambert W solves.  W has two real branches
    over the relevant domain, and they are the two answers.
    """
    # The measured rate peaks at 1/(e*tau).  Beyond that no true rate could
    # have produced this reading, on either branch.
    return np.where(m * tau <= 1 / np.e,
                    -lambertw(-m * tau, branch).real / tau,
                    np.nan)


def branch_from_perturbation(m_before, m_after):
    """Which paralyzable branch you are on, from nudging the true rate up.

    dm/dn = exp(-n*tau) * (1 - n*tau), so the sign of the measured change is
    the sign of (1 - n*tau) and nothing else.  Move the source slightly
    closer, or uncover a second one: if the reading rises you are below the
    peak, if it falls you are above it.  Exact, and it needs no calibration.
    """
    return LOW_RATE_BRANCH if m_after > m_before else HIGH_RATE_BRANCH


def relative_error_gain_non_paralyzable(m, tau):
    """Factor by which the correction inflates fractional uncertainty.

    n = m/(1-m*tau), so dn/dm = 1/(1-m*tau)^2, and after dividing through by
    n/m the fractional error is multiplied by 1/(1-m*tau).  At 50% counting
    loss your error bars double.  The correction is not free.
    """
    return 1 / (1 - m * tau)


def relative_error_gain_paralyzable(n, tau):
    """Same idea, but this one diverges at the peak.

    dm/dn = exp(-n*tau)*(1 - n*tau) vanishes at n*tau = 1, so the inverse
    slope is infinite there.  Right at the turnover the measured rate carries
    no information about the true rate at all, and no estimator can rescue
    that.  Expressed in n rather than m because it is the true rate that says
    how close to the peak you are.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.abs(1 / (1 - n * tau))

"""The two ways a counter can be blind, and the hybrid in between.

After a detector records an event it needs time to recover.  During that
window -- the dead time, tau -- particles are still arriving, but some of them
are never counted.  How the detector behaves when one of those missed
particles shows up splits the world in two:

  non-paralyzable  the missed particle is ignored completely.  The detector
                   finishes its original recovery and is live again on
                   schedule.  Losses saturate: the counter tops out at 1/tau.

  paralyzable      the missed particle still disturbs the detector and
                   restarts the clock, even though it was never recorded.  At
                   high rates the dead periods overlap continuously and the
                   reported rate *falls* -- a counter in an intense field can
                   read almost zero.

Note the asymmetry in the code below.  Paralyzable is one line, because
whether an event survives depends only on the gap to the previous *arrival*.
Non-paralyzable needs a loop, because it depends on the last *accepted* event,
and which events were accepted is exactly what we are still working out.
"""

import numpy as np


def paralyzable(times, tau):
    """Keep events that arrive at least `tau` after the previous arrival."""
    # np.diff gives the gap to the previous arrival; prepend an infinite gap so
    # the very first event is always live.
    return times[np.diff(times, prepend=-np.inf) >= tau]


def non_paralyzable(times, tau):
    """Keep events that arrive at least `tau` after the last *accepted* one."""
    kept = np.zeros(len(times), dtype=bool)
    last_accepted = -np.inf

    for i, t in enumerate(times):
        if t - last_accepted >= tau:
            kept[i] = True
            last_accepted = t

    return times[kept]


def hybrid(times, tau_fixed, tau_extending):
    """Keep events that clear a non-extending *and* an extending dead time.

    Real detectors are rarely purely one or the other: a tube may have a fixed
    recovery period plus an extending component from lingering ionisation.  An
    event must clear both to be recorded.  Several hybrid definitions exist in
    the literature; this is the simplest.
    """
    survived_extending = np.diff(times, prepend=-np.inf) >= tau_extending
    return non_paralyzable(times[survived_extending], tau_fixed)

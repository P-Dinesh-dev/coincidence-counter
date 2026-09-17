# SPEC — coincidence-gated particle counter with dead-time correction

A running record of what this project is, every decision taken, and why.
Newest work goes at the bottom.

---

## The instrument

A two-channel particle counter that does what most counters do not: reports a
rate it can actually defend.

1. **Front end** — a detector (Geiger-Müller tube, or scintillator + SiPM)
   produces a messy analogue pulse per particle.
2. **Discriminator** — a threshold turns that pulse into one clean digital edge.
3. **FPGA** — synchronises both channels, applies a programmable coincidence
   window, and counts singles and coincidences separately.
4. **Correction** — dead time and accidental coincidences are measured, not
   assumed, and removed from the reported rate.

### Why it matters

A counter that does not correct for dead time is simply wrong, and under
*paralyzable* dead time it is wrong in the dangerous direction: past a certain
field strength it reports a **falling** rate as the true rate rises. A
radiation monitor built that way reads low exactly when reading correctly
matters most. Dead-time correction is therefore a safety property, not an
accuracy refinement.

---

## Constraints

- **Budget: zero.** Every tool used is free and already on the machine.
  Physical hardware is specified but not purchased; it appears in the write-up
  as fully-specified future work.
- **Honesty of labelling.** Every figure carries `[simulated]` or
  `[hardware]`. Simulated results presented as simulated are completely
  honest; the label is what keeps them that way, so it never gets dropped.
- **Everything regenerable.** Raw data is committed, and every figure can be
  rebuilt from it by script.

---

## Environment (verified 2026-09-17)

| Tool | Version | Cost |
|---|---|---|
| Python | 3.13.14 | already installed |
| numpy | 2.4.6 | already installed |
| scipy | 1.17.1 | already installed |
| matplotlib | 3.10.9 | already installed |
| git | 2.53.0 | already installed |

Nothing needed installing. Later stages add the OSS CAD Suite (yosys,
nextpnr, Verilator, Icarus, GTKWave, SymbiYosys) — a single free download.

---

## Stage 0 — Ground truth generator ✅ PASSED

Everything downstream is validated against this stage, so it gets checked
against closed-form theory before anything else is built.

### `sim/generator.py`

`poisson_events(rate, duration, rng)` returns sorted arrival times.

**Decision — gaps, not counts.** A Poisson process can be generated two ways:
draw the number of events then scatter them uniformly, or draw the *gaps*
between events from an exponential distribution and accumulate. Both are
correct. We use gaps because dead time is itself a statement about gaps, so
the later stages want them anyway.

**Decision — the rng is passed in, never created inside.** Any experiment in
this project can then be re-run bit-identically from its seed.

**Decision — assert instead of a loop.** We draw 20% more gaps than expected
plus a floor of 1000. Rather than looping until the run is covered, we assert
the last arrival exceeds `duration`. A shortfall would silently undercount and
quietly corrupt every rate measured afterwards; failing loudly is better than
a top-up loop that hides the problem.

### `sim/deadtime.py`

Three models: `paralyzable`, `non_paralyzable`, `hybrid`.

**The asymmetry is the physics.** Paralyzable is a single vectorised line —
whether an event survives depends only on the gap to the previous *arrival*,
which is exactly `np.diff`. Non-paralyzable needs an explicit loop, because
survival depends on the last *accepted* event, and which events were accepted
is the thing still being computed. That dependency is inherent, not a coding
failure, so the loop stays and is commented as such rather than being
replaced by something clever and unreadable.

`hybrid` composes both: an event must clear a fixed non-extending dead time
*and* an extending one. Several hybrid definitions exist in the literature;
this is the simplest, and it is flagged as a choice rather than a fact.

### `sim/selftest_stage0.py` — the gate

Sweeps the true rate `n` over 18 log-spaced points and compares simulation
against theory:

- non-paralyzable `m = n/(1 + nτ)` — saturates at `1/τ`
- paralyzable `m = n·exp(-nτ)` — peaks at `n = 1/τ`, then collapses

**Decision — fixed event count, not fixed duration.** Duration is set to
`EVENTS_PER_POINT / n`, so every point on the sweep carries identical
statistical precision. With a fixed duration the low-rate points would be
hopelessly noisy and the high-rate ones needlessly precise.

**Decision — sweep stops at `nτ ≈ 3`.** Far enough past the paralyzable
turnover at `nτ = 1` to show the collapse clearly, but stopping before so few
events survive that the measurement says nothing.

**Known limitation, stated deliberately.** Residuals are scaled by `√N`, the
Poisson width. Dead time makes counts *more regular* than Poisson, so the true
spread is narrower and this scale is conservative — it could pass a
simulator that is slightly wrong. Stage 1 measures that suppression properly
via the Fano factor, which closes the gap.

### Result

```
tau = 100 us, 200,000 events per point
  non_paralyzable    max deviation  1.69 sigma
  paralyzable        max deviation  1.68 sigma
  PASS -- worst case 1.69 sigma against a 3 sigma threshold
```

Figure: `figures/stage0_deadtime_curves.png` — simulated points sit on both
theory curves across two and a half decades, including the full paralyzable
turnover and collapse.

**Gate 0 passed.**

---

## Next: Stage 1 — Estimators and the four τ methods

Inverting the curves, including the Lambert-W two-branch degeneracy: for any
measured rate below `1/(eτ)` there are **two** true rates consistent with it,
and the rate alone cannot say which. Plus four independent ways to measure τ,
cross-checked against each other.

---

## Stage 1 — Estimators and the four τ methods ✅ PASSED

Stage 0 ran forwards. This runs backwards, which is the direction a real
instrument has to work in.

### `sim/estimators.py`

**Non-paralyzable** inverts in one line, `n = m/(1-mτ)`, guarded at `mτ < 1`.
Above that ceiling the model *cannot* produce the reading at all, so the
result is `nan` rather than a large finite number — an unphysical measurement
must not silently become a plausible-looking answer.

**Paralyzable** does not invert elementarily. Taking logs of `m = n·exp(-nτ)`
leaves `ln(n)` and `n` on the same side of the equation. Substituting
`u = -nτ` turns it into `u·exp(u) = -mτ`, which is precisely the equation
Lambert W solves, giving `n = -W(-mτ)/τ`.

**The degeneracy.** W has two real branches over this domain, and both are
physically valid answers:

- `W₀` → `nτ < 1`, the low-rate branch, before the peak
- `W₋₁` → `nτ > 1`, the high-rate branch, after the peak

For any measured rate below the ceiling `1/(eτ)` there are **two** true rates
consistent with it. In the worked example they differ by **14×**. A counter
reporting 1637/s may be looking at 2,000/s or at 28,604/s, and nothing in that
number distinguishes them.

**Resolving it — `branch_from_perturbation`.** Since
`dm/dn = exp(-nτ)·(1 - nτ)`, the sign of the measured change under a small
increase in true rate is the sign of `(1 - nτ)` and nothing else. Nudge the
source closer: reading rises → below the peak; reading falls → above it.
Exact, requires no calibration, costs nothing.

**Conditioning.** `dm/dn` vanishes at `nτ = 1`, so the inverse slope is
infinite at the peak. Right at the turnover the measured rate carries *no*
information about the true rate, and no estimator can repair that. It is a
property of the physics, not of the algorithm.

### `sim/tau_methods.py` — four independent measurements

| | Method | Physics it leans on |
|---|---|---|
| A | two-source | true rates add, measured rates do not |
| B | interval distribution | a gap shorter than τ never occurs |
| C | Fano factor | dead time makes counts *too regular* |
| D | pulser injection | you already know the true rate |

**A — two sources, solved numerically.** `n₁₂ = n₁ + n₂` holds exactly for
true rates. Rather than quote a closed form from memory, we root-find the τ
that satisfies it, bracketed below the ceiling of the busiest measurement.
This also means the same function works for either dead-time model — pass it
the inversion you want.

**B — shifted exponential.** With non-paralyzable dead time an accepted event
waits τ, then waits an exponential time for the next particle. Observed gaps
are therefore `τ + Exp(n)`. For that distribution the MLE of the shift is
simply the **smallest gap observed**, and the rate follows from the mean of
what remains. Biased slightly high — the minimum of a finite sample sits just
above τ — and the bias shrinks with sample size.

**C — Fano factor, derived not assumed.** For a renewal process with gap mean
μ and variance σ², the count Fano factor over long bins tends to `σ²/μ²`.
Non-paralyzable gaps are `τ + Exp(n)`, so `μ = τ + 1/n` and `σ² = 1/n²`:

```
F = (1/n²) / (τ + 1/n)²  =  1/(1 + nτ)²
```

and since `m = n/(1 + nτ)` gives `1 - mτ = 1/(1 + nτ)`:

```
F = (1 - mτ)²        →        τ = (1 - √F) / m
```

Pure Poisson gives `F = 1`. Anything below 1 is dead time leaving fingerprints
on the *shape* of the distribution rather than on the rate. This is the method
that needs no second source and no known rate — only a long record.

**D — pulser, exact in closed form.** Both models rearrange per point with no
fitting at all:

```
non-paralyzable    1/m = 1/n + τ      →   τ = 1/m − 1/n
paralyzable        ln(n/m) = nτ       →   τ = ln(n/m)/n
```

This is the method that needs no radioactive source, only a generator whose
rate you set yourself — which is exactly why the FPGA carries one, and why
this project can be completed without buying anything.

### Bug found and fixed during Stage 1

The first draft computed the high-branch rate as `-ln(mτ)/τ`, an
"obvious" rearrangement that silently drops the `ln(n)` term. It produced
18,096/s where the truth is 28,604/s. The gate still *passed*, because the
wrong value was on the correct side of the peak and so the branch test still
came out right — a passing test hiding a wrong number.

Caught by noticing the two branches produced visibly different measured rates
(2,966 vs 1,628) when by construction they must produce the *same* one. After
the fix they read 1,647 and 1,628 — equal within noise, which is the whole
point of the degeneracy. Recorded here because the failure mode (a green test
concealing a bad derivation) is worth remembering.

### Result

```
true tau = 100.0 us (hidden from every method)

  two-source     99.92 us    -0.1%   ok
  intervals     100.00 us    +0.0%   ok
  fano           94.12 us    -5.9%   ok
  pulser         98.55 us    -1.5%   ok

  measured            1637.5 /s
  low-rate branch     2000.0 /s
  high-rate branch   28604.0 /s   (14.3x apart)
  nudge low:   1628.3 -> 1706.5  => low branch   ok
  nudge high:  1647.4 -> 1490.0  => high branch  ok
```

The Fano method carries the largest error, as expected: it measures a variance
rather than a mean, so its precision scales as `√(2/bins)` and it is the only
one of the four that is statistics-limited rather than bias-limited.

Figure: `figures/stage1_degeneracy_and_error.png`

**Gate 1 passed.**

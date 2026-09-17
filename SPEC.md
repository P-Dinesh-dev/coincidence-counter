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

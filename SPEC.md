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

---

## Stage 2 — Coincidence logic in RTL

### The Verilog

| File | Lines | Job |
|---|---|---|
| `rtl/pulse_in.v` | 33 | async detector pulse → one clean pulse in our clock domain |
| `rtl/coincidence.v` | 46 | programmable two-channel window |
| `rtl/counters.v` | 41 | three counters latched from one common instant |
| `rtl/top.v` | 41 | wiring |

**Why two flip-flops in `pulse_in`.** The discriminator has no idea our clock
exists, so it can change exactly when a flop samples it, leaving that flop
metastable — briefly neither 0 nor 1, with different readers disagreeing about
which. The first flop is *allowed* to go metastable and given a full clock
period to settle; only the second is ever read. A third stage holds the
previous value so an edge can be detected, giving one pulse per rising edge
rather than one per cycle of a wide input.

**Why the counters share one latch strobe.** If singles and coincidences were
read at different instants they would describe slightly different experiments,
and the accidental prediction below would stop meaning anything.

**Why no correction in hardware.** The FPGA counts and reports how long it
counted for. Correction happens in software where it can be inspected and
argued with. Burning an estimator into fabric would make it the one part of
the instrument nobody can check.

### `sim/rtl_model.py` — a cycle-faithful replay

Not a second design: the same logic written where it can be reasoned about.
It makes the coincidence scheme testable today without a Verilog simulator,
and later lets us demand the Verilog agree *event for event* rather than
merely look about right.

It steps only cycles on which something happens. Stepping all of them would be
10⁸ iterations per simulated second and would reveal nothing, since state only
changes when a pulse arrives.

`to_cycles` deliberately merges particles landing in the same clock cycle —
the FPGA cannot resolve finer than its own clock, so that is a real one-cycle
dead time and belongs in the model.

### Gate 2a — a prediction that could have failed ✅ PASSED

Two Poisson streams sharing no particles, so every coincidence reported is by
construction accidental. Sweep the window; theory says the rate is
`2·τ·R₁·R₂` — linear, through the origin.

```
  window     pairs  2*t*R1*R2     dev     asserts   /pairs   floor
       10      21.8       20.9   +1.50        21.8   0.9992  0.9990
       50     100.6      100.7   -0.02       100.4   0.9977  0.9950
      100     200.1      200.3   -0.14       199.2   0.9956  0.9900
      200     397.4      399.7   -0.89       393.3   0.9898  0.9802
      500     993.0      997.7   -1.14       968.5   0.9753  0.9516

  pairs vs prediction: worst 1.50 sigma against 3 -- ok
```

**Pairs versus asserts.** The formula counts *pairs*. The RTL counts *cycles
on which it raised `coincident`*, which is at most one per cycle however many
partners were in range. So asserts sit slightly below pairs, by more as the
window widens. Bounded above by the pair count and below by the case where
each pulse yields at most one assert — the measurement lands between those
bounds at every window, which is checked rather than assumed.

### Two bugs found here, both worth recording

**1. Off-by-one between the model and the RTL.** The model first used
`cycle - last <= window - 1` for the "recently fired" flag. Tracing the actual
register makes it `<= window`: a pulse at cycle `c` sets `a_left` to `window`
at `c+1`, and it decrements from there, so it stays above zero through `c+window`.

Two cycles out of `2w+1` is **10% at w=10**. Small in cycles, large in
results — and precisely the class of error the "Verilog must equal the model"
gate exists to catch.

**2. Nominal rates used where measured rates belong.** The prediction was
being fed the rates we *asked* for (10,000/s) rather than the rates the
counter actually saw (9,975 and 9,991.6/s). Poisson scatter alone puts those
0.25% apart — larger than the real effect under study. The formula takes
measured singles rates, and a real experiment has no access to the nominal
ones anyway.

**A wrong gate, also recorded.** The first version of this test asserted the
fitted intercept would sit near −0.5 cycles. That was a guess dressed as a
prediction, it failed, and the correct response was to work out what the logic
does rather than widen the threshold. The replacement gates on the quantity
theory actually predicts, with `√N` error bars.

Figure: `figures/stage2_accidentals.png`

### Gate 2b — Verilog equals the model ⏸ BLOCKED

Needs an HDL simulator. None is installed, and WSL has no distribution.
Neither costs money; both cost bandwidth, so the choice is the user's.
The RTL and the model are both written and waiting.

---

## Stage 2b — Verilog equals the model ✅ PASSED

### cocotb abandoned, and why

The plan called for cocotb. It does not work on this machine: `vvp.exe` cannot
load cocotb's VPI library because this is the **Microsoft Store build of
Python**, whose `python313.dll` lives in a restricted `WindowsApps` directory
that a non-Python process cannot load from. Failure code `0xC0000135`,
`STATUS_DLL_NOT_FOUND`.

Rather than install a second Python, the testbench drives the RTL from a
**stimulus file**. Python writes one line per clock cycle, Icarus replays it
through the real Verilog, and the count comes back on stdout. Fewer moving
parts, no Python inside the simulator, and it proves exactly the same thing.

`tb/tb_coincidence.v` samples on the **falling** edge. By then the rising edge
has latched the previous cycle's state and this cycle's inputs have settled,
so the combinational output belongs entirely to one cycle. Sampling on the
rising edge would straddle two and miscount — this was caught by reasoning
about it before running, and the reasoning is written into the file.

### Result

```
3,931 and 3,909 pulses over 199,987 cycles

 window    verilog      model   verdict
      1        227        227   equal
      2        364        364   equal
      5        797        797   equal
     17      2,269      2,269   equal
     50      4,931      4,931   equal
    200      7,619      7,619   equal
```

Exact agreement at every window, `window = 1` included — the boundary case
where the off-by-one found in Stage 2 would have shown up. The Verilog and the
model now confirm each other.

**Gate 2b passed.**

---

## Stage 3 — Implementation evidence, no board ✅ PASSED

The honest substitute for owning hardware. It does not prove the design
*runs* — only silicon proves that — but it establishes that the logic maps to
a real device, fits, and closes timing at a stated clock, using the same tools
that would build the bitstream.

### Three real problems found by trying to build it

**1. The top level did not fit.** Three 32-bit counters brought out as pins
need 96 IO; the target package has 39. Place-and-route failed with
`Unable to find a placement location`. The fix was the UART that was in the
plan all along — `rtl/uart_tx.v` and `rtl/readout.v` serialise the twelve
bytes out of one pin. The coincidence window became a synthesis parameter for
the same reason: as a port it would have cost sixteen more pins.

Final IO count: **7**. This is why synthesis belongs in the loop and not at
the end.

**2. The design closed at only 31.9 MHz.** The critical path report named it
exactly: `b_left` flop → decrement → a 16-bit `> 0` reduction → `coincident` →
the 32-bit counter carry chain.

The fix replaces the combinational comparison with a registered `a_active`
flag carrying identical information, computed one cycle early where the answer
is already being worked out. **31.9 → 40.1 MHz on the same part.** Gate 2b was
re-run immediately afterwards and still gives exact agreement — which is the
entire reason for having a gate that demands exactness rather than plausibility.

**3. Yosys's ABC9 backend crashes on this build.** Both `synth_ice40` and
`synth_ecp5` abort inside the experimental `write_xaiger2` backend
(`Assert 'data_start == f->tellp()' failed`). Not a property of this design.
`synth/ice40.ys` splits the flow and does LUT mapping with classic
`abc -lut 4` instead; the rest of the stock flow runs unchanged. Note that
`-noabc` is *not* a workaround — it leaves `$_ANDNOT_` cells that nextpnr
refuses to place.

### Result

```
Synthesis (yosys, iCE40)
  LUT4            301
  flip-flops      370
  carry cells     141

Place and route (up5k, sg48)      low-power part
  logic cells   539/5280  (10%)
  Fmax          40.05 - 43.28 MHz over 6 seeds (median 41.90)
  timing resolution at median Fmax: 23.9 ns

Place and route (hx8k, ct256)     speed part
  logic cells   539/7680  (7%)
  Fmax          93.21 - 102.24 MHz over 6 seeds (median 98.20)
  closes at 100 MHz on 2/6 seeds
  timing resolution at median Fmax: 10.2 ns
```

**Seeds, reported in full and deliberately.** Placement is stochastic. On
hx8k the design closes at 100 MHz on two seeds out of six and misses on four.
Quoting only the 102.24 MHz run would be picking the lucky one and calling it
the answer. The honest statement is that this design is **marginal at 100 MHz
on hx8k and comfortable at ~42 MHz on up5k**.

**That margin is not a failure, because 100 MHz was never a requirement.** The
clock sets timing resolution, and the physics sets what resolution is needed:
coincidence windows for a muon telescope run from ~100 ns to several µs, so
even the up5k's 23.9 ns is comfortably finer than required. The number that
matters is stated, not a target that was assumed.

Reports: `synth/reports/` — regenerate with `python synth/run_synth.py`.

**Gate 3 passed.**

---

## Stage 4 — Validation against data we did not generate ✅ PASSED

Every earlier stage checked our work against simulations we wrote ourselves,
which can only confirm that our algebra is self-consistent. This stage runs
the pipeline over **62.8 hours of real cosmic-ray muon data** from a
CosmicWatch v3X detector (`ATTRIBUTION.md`), and it is the first thing here
that could tell us something we did not put in.

It did.

### The recording

```
events        687,941
duration      226,189 s  (62.8 h)
raw rate      3.0414 /s
coincident    84,463 (12.3%)
m*tau         0.00124   -- this detector is almost never busy
```

The detector logs its own accumulated dead time per event: mean **408.2 µs**,
sd 19.0 µs, range 331–650 µs. So there is an independent number to test our
estimators against rather than one we chose.

### Cross-check: two routes to the same formula

The CosmicWatch analysis divides counts by *live time*. This project inverts
`m = n/(1+nτ)`. These are the same statement:

```
N / (T - N·τ)   ==   m / (1 - m·τ)      with m = N/T
```

Both give **3.04523 /s** from a raw 3.04145 /s, agreeing to 2 parts in 10⁹.
Two people reaching the same formula from opposite directions is a small but
real check that neither has misremembered it.

### The finding: dead time the detector does not report

Define **slack** = (gap between events) − (dead time the detector booked). If
the reported dead time were the whole story, slack is just the wait for the
next muon: exponential, mean 329 ms, populated all the way down to zero. Over
688k events its minimum should sit around **0.48 µs**.

The observed minimum slack is **57.0 µs**. Not one event in 687,941 arrived
sooner than that after the reported dead period ended.

```
shortest gap ever seen          456.0 us
shortest slack                   57.0 us
expected if only reported         0.48 us
negative slack (bookkeeping)        0
```

Under the exponential hypothesis the probability of that is `exp(-119)`,
about **10⁻⁵²**. The detector therefore blocks for roughly **57 µs longer
than it reports** — about 14% beyond its own figure. The figure shows it
plainly: the data tracks the exponential expectation exactly above 57 µs and
is *empty* below it.

This is not a criticism of CosmicWatch; ~14% unreported blocking is
immaterial at `mτ = 0.001`. It is the point of the exercise: an estimator
built from timestamps alone found something the instrument's own accounting
missed.

### What that does to our four methods

| | value | vs reported | vs effective |
|---|---|---|---|
| reported (detector) | 408.2 µs | — | — |
| **effective** (reported + slack) | **465.2 µs** | — | — |
| **B — intervals** | 456.0 µs | +11.7% | **−2.0%** |
| **C — Fano** | 407.5 µs ± 11,991 µs | — | — |

**Method B was not wrong.** Judged against the reported dead time it looks
11.7% off; judged against the blocking that actually occurred it is within
**2.0%**. It measures what the counter did, not what the counter said.

**Method C is useless here, and says so.** Its error bar is ±11,991 µs on a
407 µs answer — 29× the quantity being measured. At `mτ = 0.0014` the variance
suppression it relies on (`F = 0.9975`) is far smaller than the scatter in `F`
itself. Its apparent 0.2% agreement in the first draft of this analysis was
**pure coincidence**, and was reported as a success until the error bar was
computed.

That near-miss is why `tau_from_fano` was changed to return its uncertainty
alongside its answer. An estimator that returns a number without an error bar
in a regime where it has no power is the dangerous kind of wrong: it looks
like a confirmation.

### A first draft that was wrong, recorded

The first version of this analysis printed an explanation that Method B
"estimates the floor of the dead-time distribution". That sounded reasonable
and was false: 456 µs is *above* both the 331 µs minimum and the 408 µs mean,
so it cannot be estimating a floor. Checking the arithmetic — if τ were
constant at 408 µs the shortest gap over 688k events should be ≈408.5 µs —
is what exposed the 57 µs excess. The wrong explanation was load-bearing
until it was tested.

Figure: `figures/stage4_real_data.png`

**Gate 4 passed.**

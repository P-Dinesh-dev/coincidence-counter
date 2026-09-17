"""Gate 2b: the Verilog must agree with the model, count for count.

One list of arrival times feeds both: it is written out as a stimulus file for
Icarus to replay through the real RTL, and handed to sim/rtl_model.py for the
expected answer.  A single ground truth, two implementations of it, and
"close enough" is not a pass.

Nothing about the expected answer lives in this file.  It comes from the
model, which was itself written by reading the Verilog.  If either one drifts,
this notices.

    python tb/run_tb.py        (needs iverilog on PATH)
"""

import pathlib
import re
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.generator import poisson_events
from sim.rtl_model import to_cycles, count_coincidences

TB = ROOT / "tb"
CLK_HZ = 100e6
DURATION = 2e-3         # 200,000 cycles: busy enough to be a real test
RATE = 2_000_000.0     # deliberately high, so coincidences are plentiful
WINDOWS = [1, 2, 5, 17, 50, 200]
SEED = 20260917


def write_stimulus(a_cycles, b_cycles, last_cycle):
    """One line per clock cycle, "a b" -- the dumbest format that works.

    A sparse format would be smaller, but then the Verilog would need to track
    which cycle it was on and skip forward, which is logic in the testbench,
    which is somewhere for a bug to hide.
    """
    a_flags = np.zeros(last_cycle + 1, dtype=np.uint8)
    b_flags = np.zeros(last_cycle + 1, dtype=np.uint8)
    a_flags[a_cycles] = 1
    b_flags[b_cycles] = 1

    np.savetxt(TB / "stim.txt", np.column_stack([a_flags, b_flags]), fmt="%d")
    return len(a_flags)


def run_icarus(window):
    """Simulate at one window setting and pull the count back out."""
    result = subprocess.run(
        ["vvp", str(TB / "sim.vvp"), f"+window={window}"],
        cwd=TB, capture_output=True, text=True, check=True,
    )
    match = re.search(r"RESULT window=(\d+) count=(\d+)", result.stdout)
    if not match:
        raise RuntimeError(f"no RESULT line in:\n{result.stdout}\n{result.stderr}")
    return int(match.group(2))


def main():
    rng = np.random.default_rng(SEED)
    a = to_cycles(poisson_events(RATE, DURATION, rng), CLK_HZ)
    b = to_cycles(poisson_events(RATE, DURATION, rng), CLK_HZ)
    last_cycle = int(max(a[-1], b[-1]))

    cycles = write_stimulus(a, b, last_cycle)
    print(f"Gate 2b   {len(a):,} and {len(b):,} pulses over {cycles:,} cycles\n")

    subprocess.run(
        ["iverilog", "-o", str(TB / "sim.vvp"),
         str(TB / "tb_coincidence.v"), str(ROOT / "rtl" / "coincidence.v")],
        check=True,
    )

    print(f"  {'window':>7} {'verilog':>10} {'model':>10}   verdict")
    all_equal = True
    for window in WINDOWS:
        from_verilog = run_icarus(window)
        from_model = count_coincidences(a, b, window)
        equal = from_verilog == from_model
        all_equal &= equal
        print(f"  {window:7d} {from_verilog:10,d} {from_model:10,d}   "
              f"{'equal' if equal else 'MISMATCH'}")

    print(f"\n  {'PASS' if all_equal else 'FAIL'} -- "
          f"{'exact agreement at every window' if all_equal else 'the two disagree'}")
    return all_equal


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

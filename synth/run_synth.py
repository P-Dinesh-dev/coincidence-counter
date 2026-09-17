"""Stage 3: synthesise, place, route, and report what the design actually costs.

This is the honest substitute for owning a board.  It does not prove the
design runs -- only silicon proves that -- but it does establish that the
logic maps to a real device, fits in it, and closes timing at a stated clock,
using the same tools that would build the bitstream.

Placement is stochastic, so each target is run across several seeds and the
whole spread is reported.  Quoting only the best seed would be picking the
lucky run and calling it the answer.

    python synth/run_synth.py        (needs yosys and nextpnr-ice40 on PATH)
"""

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYNTH = ROOT / "synth"
REPORTS = SYNTH / "reports"

TARGETS = [("up5k", "sg48"), ("hx8k", "ct256")]
SEEDS = [1, 2, 3, 4, 5, 6]
TARGET_MHZ = 100.0


def synthesise():
    """Run yosys and pull the cell counts out of its statistics."""
    log = subprocess.run(
        ["yosys", "-s", str(SYNTH / "ice40.ys")],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    (REPORTS / "yosys_ice40.log").write_text(log, encoding="utf-8")

    cells = {}
    for name in ("SB_LUT4", "SB_CARRY", "SB_DFFE", "SB_DFFESR",
                 "SB_DFFESS", "SB_DFFSR"):
        found = re.findall(rf"^\s+(\d+)\s+{name}\s*$", log, re.MULTILINE)
        if found:
            cells[name] = int(found[0])
    return cells


def place_and_route(device, package, seed):
    """Run nextpnr once and return (fmax_mhz, logic_cells_used, cells_total)."""
    result = subprocess.run(
        ["nextpnr-ice40", f"--{device}", "--package", package,
         "--json", str(SYNTH / "top_ice40.json"),
         "--pcf-allow-unconstrained", "--freq", str(TARGET_MHZ),
         "--seed", str(seed)],
        cwd=ROOT, capture_output=True, text=True,
    )
    log = result.stdout + result.stderr
    if seed == SEEDS[0]:
        (REPORTS / f"nextpnr_{device}.log").write_text(log, encoding="utf-8")

    fmax = re.search(r"Max frequency for clock[^:]*:\s*([0-9.]+)\s*MHz", log)
    used = re.search(r"ICESTORM_LC:\s*(\d+)/\s*(\d+)", log)
    if not (fmax and used):
        raise RuntimeError(f"could not parse nextpnr output for {device}/{seed}")
    return float(fmax.group(1)), int(used.group(1)), int(used.group(2))


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    lines = []

    cells = synthesise()
    flops = sum(v for k, v in cells.items() if k.startswith("SB_DFF"))
    lines.append("Synthesis (yosys, iCE40)")
    lines.append(f"  LUT4          {cells['SB_LUT4']:5d}")
    lines.append(f"  flip-flops    {flops:5d}")
    lines.append(f"  carry cells   {cells['SB_CARRY']:5d}")
    lines.append("")

    for device, package in TARGETS:
        results = [place_and_route(device, package, s) for s in SEEDS]
        freqs = [f for f, _, _ in results]
        used, total = results[0][1], results[0][2]

        closes = sum(f >= TARGET_MHZ for f in freqs)
        lines.append(f"Place and route ({device}, {package})")
        lines.append(f"  logic cells   {used}/{total}  "
                     f"({100 * used / total:.0f}%)")
        lines.append(f"  Fmax          {min(freqs):.2f} - {max(freqs):.2f} MHz "
                     f"over {len(SEEDS)} seeds (median {sorted(freqs)[len(freqs) // 2]:.2f})")
        lines.append(f"  closes at {TARGET_MHZ:.0f} MHz on {closes}/{len(SEEDS)} seeds")
        lines.append(f"  timing resolution at median Fmax: "
                     f"{1000 / sorted(freqs)[len(freqs) // 2]:.1f} ns")
        lines.append("")

    report = "\n".join(lines)
    (REPORTS / "summary.txt").write_text(report, encoding="utf-8")
    print(report)
    print(f"written to {REPORTS / 'summary.txt'}")


if __name__ == "__main__":
    main()

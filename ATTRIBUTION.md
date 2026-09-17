# Attribution

## Data

`validation/AxLab_C_001.txt` — 62.8 hours of cosmic-ray muon events recorded
by a **CosmicWatch Desktop Muon Detector v3X** (detector "AxLab"), taken from
the project's public repository:

> https://github.com/spenceraxani/CosmicWatch-Desktop-Muon-Detector-v3X

Licensed **CC BY-NC 4.0**. Used here unmodified, for non-commercial academic
work. The file is redistributed in this repository so that every figure in
this project can be regenerated from committed inputs.

The CosmicWatch detector design and papers:

- S. N. Axani et al., *The CosmicWatch Desktop Muon Detector: a self-contained,
  pocket sized particle detector*, arXiv:1801.03029
- S. N. Axani, *The Physics Behind the CosmicWatch Desktop Muon Detectors*,
  arXiv:1908.00146
- *CosmicWatch: The Desktop Muon Detector (v3X)*, arXiv:2508.12111

The `Flag` column was confirmed to be the coincidence flag by reading
`Data/plot.py` in that repository, not by assumption.

**Nothing in this project's own hardware or software is derived from the
CosmicWatch design.** The RTL, the estimators and the analysis are original.
CosmicWatch is used here solely as a source of real recorded data against
which to test this pipeline.

## Tools

All free and open source:

- **Yosys, nextpnr, Icarus Verilog, GTKWave** — via the
  [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build), ISC and
  other permissive licences
- **numpy, scipy, matplotlib** — BSD

## Prior art consulted

- **Stingray** (`stingray.deadtime`) — the reference implementation of
  dead-time modelling in X-ray astronomy, including the Zhang+95 paralyzable
  treatment. Read for orientation; no code was copied.

"""Generate self-contained PDB fixtures for the MockProvider.

Idealized poly-alanine alpha-helices (rough geometry — enough for Mol* to render
a backbone/cartoon offline). Run: `python backend/app/data/fixtures/_generate.py`.
Produces monomer.pdb (chain A) and complex.pdb (chains A + B).
"""
from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


def atom_line(serial: int, name: str, resname: str, chain: str, resseq: int,
              x: float, y: float, z: float, element: str) -> str:
    if len(name) >= 4:
        nm = name[:4]
    elif len(element) == 1:
        nm = f" {name:<3s}"
    else:
        nm = f"{name:<4s}"
    return (
        f"ATOM  {serial:>5d} {nm} {resname:>3s} {chain:1s}{resseq:>4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}          {element:>2s}"
    )


def helix(chain: str, n: int, x0: float = 0.0, y0: float = 0.0,
          start_serial: int = 1, start_res: int = 1) -> tuple[list[str], int]:
    lines: list[str] = []
    serial = start_serial
    radius = 2.3
    for i in range(n):
        ang = math.radians(i * 100.0)
        z = i * 1.5
        ca = (x0 + radius * math.cos(ang), y0 + radius * math.sin(ang), z)
        n_ = (x0 + radius * math.cos(ang - 0.4), y0 + radius * math.sin(ang - 0.4), z - 0.55)
        c_ = (x0 + radius * math.cos(ang + 0.4), y0 + radius * math.sin(ang + 0.4), z + 0.55)
        o_ = (x0 + (radius + 0.3) * math.cos(ang + 0.55),
              y0 + (radius + 0.3) * math.sin(ang + 0.55), z + 0.70)
        resseq = start_res + i
        for name, coord, elem in (("N", n_, "N"), ("CA", ca, "C"), ("C", c_, "C"), ("O", o_, "O")):
            lines.append(atom_line(serial, name, "ALA", chain, resseq, coord[0], coord[1], coord[2], elem))
            serial += 1
    return lines, serial


def main() -> None:
    mono, _ = helix("A", 16)
    (OUT / "monomer.pdb").write_text("\n".join(mono + ["TER", "END"]) + "\n")

    a, next_serial = helix("A", 14, x0=0.0)
    b, _ = helix("B", 12, x0=14.0, start_serial=next_serial + 1, start_res=1)
    (OUT / "complex.pdb").write_text("\n".join(a + ["TER"] + b + ["TER", "END"]) + "\n")

    print("wrote", OUT / "monomer.pdb", "and", OUT / "complex.pdb")


if __name__ == "__main__":
    main()

"""Chester: faces coloured by z_zmin (1.1.0 subgrid), the links the ENGINE blocks for a weir file (crests.npz from
engine_count.py), and the weir line. Args: <weirfile> <crests.npz>. Writes <stem>_links.png + prints blocked links whose
both faces are creek faces (z_zmin < 1.0 m). Read-only."""
import sys
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R = Path("/cache/home/tpj8/nj_bight_sfincs"); H = Path(__file__).resolve().parent
sys.path.insert(0, str(R / "logs/bed_audit_2026-11-05/checks/levee_continuity")); import lib as Lb
RUN = R / "experiments/v4_refreeze_swz_v11/p4-premier+weir-elizabeth-rahway"
mesh = Lb.Mesh(RUN)
X0, X1, Y0, Y1 = 467900, 469300, 4410900, 4411900
s = np.where((mesh.fx > X0) & (mesh.fx < X1) & (mesh.fy > Y0) & (mesh.fy < Y1) & mesh.active)[0]
d = np.load(sys.argv[2]); eu = d["eu"]; eh = d["eh"]
mx = .5 * (mesh.fx[mesh.nm[eu]] + mesh.fx[mesh.nmu[eu]]); my = .5 * (mesh.fy[mesh.nm[eu]] + mesh.fy[mesh.nmu[eu]])
inb = (mx > X0) & (mx < X1) & (my > Y0) & (my < Y1); eu, eh = eu[inb], eh[inb]
fig, ax = plt.subplots(figsize=(13, 10))
sc = ax.scatter(mesh.fx[s], mesh.fy[s], c=mesh.z_zmin[s], s=np.clip(mesh.area[s] / 30, 4, 120), cmap="terrain", vmin=-3, vmax=6, marker="s")
plt.colorbar(sc, shrink=.6, label="z_zmin (1.1.0)")
creek = 0
for u, h in zip(eu, eh):
    a, b = mesh.nm[u], mesh.nmu[u]
    both = mesh.z_zmin[a] < 1.0 and mesh.z_zmin[b] < 1.0
    creek += both
    ax.plot([mesh.fx[a], mesh.fx[b]], [mesh.fy[a], mesh.fy[b]], "-", c="r" if both else "k", lw=2.5 if both else 1)
sys.path.insert(0, str(R / "logs/refreeze_2026-10-06/structures")); from weir_on_mesh import read_weir
for name, rows in read_weir(sys.argv[1]): ax.plot(rows[:, 0], rows[:, 1], "b-", lw=1.5)
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal")
ax.set_title(f"{Path(sys.argv[1]).name}: {len(eu)} blocked links in view, RED = creek-to-creek (both z_zmin < 1 m): {creek}")
out = H / (Path(sys.argv[1]).stem + "_links.png"); fig.savefig(out, dpi=100, bbox_inches="tight"); print(out, "creek-creek blocked", creek)

"""Trace a dike crest on the 3 m UTM CUDEM window saved by site_view.py: walk from p0 to p1 (hand-picked on the crest)
every `step` m, and at each station take the highest pixel on a +-`half` m transect square to the walk. Returns
(x, y, z) of the crest points. The ends are picked by eye; the trace only follows the ridge between them."""
import numpy as np


def load(npz):
    d = np.load(npz)
    a, b, c, dd, e, f = d["transform"]
    return d["z"], (a, b, c, dd, e, f)


def sample(z, t, x, y):
    a, b, c, d, e, f = t
    col = ((x - c) / a).astype(int)
    row = ((y - f) / e).astype(int)
    ok = (row >= 0) & (row < z.shape[0]) & (col >= 0) & (col < z.shape[1])
    out = np.full(x.shape, np.nan)
    out[ok] = z[row[ok], col[ok]]
    return out


def trace(npz, p0, p1, step=5.0, half=15.0):
    z, t = load(npz)
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    L = np.hypot(*(p1 - p0))
    u = (p1 - p0) / L
    nrm = np.array([-u[1], u[0]])
    out = []
    for s in np.arange(0, L + 1e-6, step):
        c = p0 + u * s
        o = np.arange(-half, half + 0.1, 1.5)
        xs, ys = c[0] + nrm[0] * o, c[1] + nrm[1] * o
        v = sample(z, t, xs, ys)
        k = int(np.nanargmax(v))
        out.append((xs[k], ys[k], v[k]))
    return np.array(out)

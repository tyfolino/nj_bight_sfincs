"""Execute a notebook in place, logging the kernel's peak memory PER CELL.

    python scripts/render_notebook_profiled.py notebooks/v3/sandy-v3-viz-2026-09-14.ipynb

Same result as ``jupyter nbconvert --to notebook --execute --inplace``, plus one line per
cell on stderr: index, wall seconds, and the peak resident set of the kernel process tree
while that cell ran. Written after the 2026-09-14 epoch render was OOM-killed at 100 G with
``DeadKernelError`` and nothing to say which cell did it (``sacct`` MaxRSS is a 30 s sample
and reads 32 G). The sampler is a thread polling ``psutil`` every 0.25 s; the executed
notebook is written even when a cell fails (``allow_errors`` off — the failing cell is the
last one recorded), so a partial render is still readable.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import nbformat
import psutil
from nbclient import NotebookClient


class _Sampler(threading.Thread):
    def __init__(self, interval: float = 0.25):
        super().__init__(daemon=True)
        self.interval = interval
        self.pid: int | None = None
        self.peak = 0
        self.overall = 0
        self._stop = threading.Event()

    def rss(self) -> int:
        if self.pid is None:
            return 0
        try:
            k = psutil.Process(self.pid)
            procs = [k, *k.children(recursive=True)]
        except psutil.Error:
            return 0
        tot = 0
        for p in procs:
            try:
                tot += p.memory_info().rss
            except psutil.Error:
                pass
        return tot

    def run(self):
        while not self._stop.is_set():
            r = self.rss()
            self.peak = max(self.peak, r)
            self.overall = max(self.overall, r)
            time.sleep(self.interval)

    def reset(self) -> None:
        self.peak = self.rss()
        self.overall = max(self.overall, self.peak)

    def stop(self) -> None:
        self._stop.set()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook", type=Path)
    ap.add_argument("--timeout", type=int, default=3600, help="per-cell seconds")
    ap.add_argument("--interval", type=float, default=0.25, help="sampler period, s")
    args = ap.parse_args(argv)

    nb = nbformat.read(args.notebook, as_version=4)
    client = NotebookClient(
        nb,
        timeout=args.timeout,
        kernel_name=nb.metadata.get("kernelspec", {}).get("name", "python3"),
        resources={"metadata": {"path": str(args.notebook.parent)}},
    )
    sampler = _Sampler(args.interval)
    t0 = {}

    def on_start(cell=None, cell_index=None, **_):
        if sampler.pid is None and client.km is not None:
            sampler.pid = client.km.provisioner.process.pid  # type: ignore[union-attr]
        sampler.reset()
        t0[cell_index] = time.time()
        head = "".join(cell.get("source", "")).strip().splitlines()[:1]
        print(
            f"[cell {cell_index:2d}] start   {head[0][:70] if head else ''}",
            file=sys.stderr,
            flush=True,
        )

    def on_done(cell=None, cell_index=None, **_):
        dt = time.time() - t0.get(cell_index, time.time())
        print(
            f"[cell {cell_index:2d}] done    {dt:7.1f} s  peak RSS "
            f"{sampler.peak / 2**30:6.1f} G",
            file=sys.stderr,
            flush=True,
        )

    client.on_cell_start = on_start
    client.on_cell_executed = on_done
    sampler.start()
    try:
        client.execute()
    finally:
        sampler.stop()
        nbformat.write(nb, args.notebook)
        print(
            f"peak RSS over the run {sampler.overall / 2**30:.1f} G; wrote "
            f"{args.notebook}",
            file=sys.stderr,
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

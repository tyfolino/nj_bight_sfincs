#!/bin/bash
# Build SFINCS natively from ~/nj_sandy_sfincs/SFINCS-src (tag v2.3.3 + our branch) so the
# SnapWave wind-direction bug (FINDINGS §43) can be patched and the engine re-run WITHOUT a
# container. Written 2026-09-11, plan Phase 1a.
#
#   hpc/build_sfincs_native.sh <variant> [--fc host|conda] [--src DIR] [-j N] [--force]
#
#   variant   install name, e.g. v2.3.3-unpatched-gf11, v2.3.3-winddir-fix-1-gf11
#   --fc      host  = /usr/bin/gfortran 11.5 (DEFAULT — one patch level from the container's
#                     Ubuntu-jammy gfortran 11.4, so the closest shot at a bit-identical gate)
#             conda = the sfincs-build env's gfortran 16.2 (five majors newer)
#   --src     source checkout (default ~/nj_sandy_sfincs/SFINCS-src)
#   -j        make parallelism for the bundled netcdf-fortran (default 16); src/ is serial
#   --force   rebuild even when the install already matches this source + flags
#
# Installs to  ~/nj_sandy_sfincs/sfincs-native/<variant>/bin/sfincs   (small; home)
# Builds in    /scratch/tpj8/sfincs-build/<variant>/                  (rsync'd copy; scratch)
# so the git checkout stays CLEAN — configure/make never run inside SFINCS-src.
#
# What Deltares does (source/build_scripts/Dockerfile + Singularityfile-cpu.def, the recipe
# behind sfincs-cpu.sif): Ubuntu jammy, apt gfortran (11.4) + libnetcdf-dev,
#   FCFLAGS="-fopenmp -O3 -fallow-argument-mismatch -w"  (FFLAGS the same)
#   autoreconf -ivf && ./configure --disable-openacc && make && make install
# The tree bundles netcdf-fortran 4.6.1 (third_party_open/netcdf) and builds it in place
# with the SAME Fortran compiler, so .mod-file compatibility is never an issue; only the
# netCDF *C* library is external (here: the sfincs-build conda env, rpath baked in — no
# LD_LIBRARY_PATH needed at run time; SFINCS_BIN_LIBDIR stays available as an override).
# `-fallow-argument-mismatch` is for netcdf-fortran issue #212, and `-w` silences the
# warnings gfortran ≥ 10 raises on that code. We use the identical flags.
#
# Output: prints the binary's sha256, its RUNPATH, and `ldd`; writes BUILD_INFO beside it
# with the source commit, `git diff --stat` (non-empty = a patched tree), compiler version,
# flags, host and date. scripts/record_engine.py (Phase 1b) reads BUILD_INFO.

set -euo pipefail

VARIANT="${1:?usage: build_sfincs_native.sh <variant> [--fc host|conda] [--src DIR] [-j N] [--force]}"
shift
FC_KIND=host
SRC="$HOME/nj_sandy_sfincs/SFINCS-src"
JOBS=16
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --fc) FC_KIND="$2"; shift 2 ;;
        --src) SRC="$2"; shift 2 ;;
        -j) JOBS="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

ENV="$HOME/nj_sandy_sfincs/micromamba/envs/sfincs-build"
PREFIX="$HOME/nj_sandy_sfincs/sfincs-native/$VARIANT"
BUILD="/scratch/tpj8/sfincs-build/$VARIANT"
case "$FC_KIND" in
    host)  FC=/usr/bin/gfortran; CC=/usr/bin/gcc ;;
    conda) FC="$ENV/bin/x86_64-conda-linux-gnu-gfortran"; CC="$ENV/bin/x86_64-conda-linux-gnu-gcc" ;;
    *) echo "--fc must be host or conda" >&2; exit 2 ;;
esac
[ -x "$FC" ] || { echo "no Fortran compiler at $FC" >&2; exit 2; }
[ -d "$ENV/lib/pkgconfig" ] || { echo "no sfincs-build env at $ENV" >&2; exit 2; }
[ -f "$SRC/source/configure.ac" ] || { echo "no SFINCS source at $SRC" >&2; exit 2; }

FLAGS="-fopenmp -O3 -fallow-argument-mismatch -w"
SRC_HEAD=$(git -C "$SRC" rev-parse HEAD)
SRC_DIFF=$(git -C "$SRC" diff --stat HEAD -- source | tail -n 1)
SRC_DIFF_SHA=$(git -C "$SRC" diff HEAD -- source | sha256sum | cut -c1-16)
STAMP="src=$SRC_HEAD diff=$SRC_DIFF_SHA fc=$FC_KIND flags=[$FLAGS]"

if [ "$FORCE" -eq 0 ] && [ -x "$PREFIX/bin/sfincs" ] && grep -qF "$STAMP" "$PREFIX/BUILD_INFO" 2>/dev/null; then
    echo "up to date: $PREFIX/bin/sfincs already built from $STAMP"
    sha256sum "$PREFIX/bin/sfincs"
    exit 0
fi

echo "== SFINCS native build: $VARIANT"
echo "   source   $SRC @ ${SRC_HEAD:0:12}  (${SRC_DIFF:-clean tree})"
echo "   compiler $FC  ($("$FC" --version | head -n 1))"
echo "   netcdf-c $ENV  ($("$ENV/bin/pkg-config" --modversion netcdf 2>/dev/null || echo '?'))"
echo "   build    $BUILD"
echo "   install  $PREFIX"
echo "   host     $(hostname)   jobs $JOBS"

# Fresh build tree from the checkout — configure/make never touch the git tree.
mkdir -p "$BUILD" "$PREFIX"
rsync -a --delete --exclude .git "$SRC/source/" "$BUILD/"
cd "$BUILD"
find . -name '*.m4' -o -name '*.ac' -o -name '*.am' -o -name '*.f90' -o -name '*.F90' \
    | xargs -r sed -i 's/\r$//'      # Deltares' build_gfortran_cpu.sh does dos2unix too

export PATH="$ENV/bin:$PATH"          # autoconf/automake/libtool/m4/pkg-config from conda
export PKG_CONFIG_PATH="$ENV/lib/pkgconfig"
export CPPFLAGS="-I$ENV/include"
export LDFLAGS="-L$ENV/lib -Wl,-rpath,$ENV/lib"
export FCFLAGS="$FLAGS" FFLAGS="$FLAGS"
export FC CC F77="$FC"

autoreconf -ivf > autoreconf.log 2>&1 || { tail -n 40 autoreconf.log; exit 1; }
./configure --disable-openacc --prefix="$PREFIX" > configure.log 2>&1 \
    || { tail -n 60 configure.log; exit 1; }
# 🔴 src/ must build SERIALLY: src/Makefile.am lists the Fortran sources in dependency
# order but declares no .mod dependencies, so `make -jN` there races ("Cannot open module
# file 'sfincs_log.mod'"). Deltares builds with a plain `make`. The bundled netcdf-fortran
# has proper dependencies and takes the parallelism.
make -j"$JOBS" -C third_party_open/netcdf/netcdf-fortran-4.6.1 > make_netcdff.log 2>&1 \
    || { tail -n 80 make_netcdff.log; exit 1; }
make -j1 > make.log 2>&1 || { tail -n 80 make.log; exit 1; }
make install > install.log 2>&1 || { tail -n 40 install.log; exit 1; }

BIN="$PREFIX/bin/sfincs"
[ -x "$BIN" ] || { echo "no binary at $BIN after install" >&2; exit 1; }
{
    echo "variant   $VARIANT"
    echo "built     $(date -Is) on $(hostname)"
    echo "source    $SRC"
    echo "commit    $SRC_HEAD"
    echo "branch    $(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
    echo "diffstat  ${SRC_DIFF:-clean tree}"
    echo "compiler  $FC  $("$FC" --version | head -n 1)"
    echo "netcdf-c  $("$ENV/bin/pkg-config" --modversion netcdf)  ($ENV)"
    echo "flags     $FLAGS"
    echo "configure --disable-openacc --prefix=$PREFIX"
    echo "sha256    $(sha256sum "$BIN" | cut -d' ' -f1)"
    echo "stamp     $STAMP"
} > "$PREFIX/BUILD_INFO"

echo "== built $BIN"
sha256sum "$BIN"
readelf -d "$BIN" | grep -E 'RUNPATH|RPATH' || echo "   (no RUNPATH — check LDFLAGS)"
ldd "$BIN" | grep -E 'netcdf|gfortran|gomp|hdf5|not found' || true
echo "== BUILD_INFO"
cat "$PREFIX/BUILD_INFO"

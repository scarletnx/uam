#!/bin/sh
# tests/run.sh UAM ENVYDIS OUTDIR: compiles each shader of tests/ubo/ with UAM, disassembles its code with envytools'
# ENVYDIS into OUTDIR and runs it with tests/sasseval.py, which checks every word the shader stores.
# Exit 0 when every shader stores what its "// expect:" line says.
set -u
[ $# -eq 3 ] || { echo "usage: tests/run.sh UAM ENVYDIS OUTDIR" >&2; exit 2; }
uam=$1 envydis=$2 out=$3
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out" || exit 2
failed=0
for shader in "$here"/ubo/*.comp; do
    name=$(basename "$shader" .comp)
    if ! "$uam" -s comp -o "$out/$name.dksh" -r "$out/$name.raw" "$shader" > "$out/$name.log" 2>&1; then
        echo "$name: uam failed:"; cat "$out/$name.log"; failed=1; continue
    fi
    "$envydis" -m gm107 -i -n < "$out/$name.raw" > "$out/$name.sass" || { echo "$name: envydis failed"; failed=1; continue; }
    python3 -B "$here/sasseval.py" "$shader" "$out/$name.sass" || failed=1
done
exit $failed

#!/usr/bin/env python3
"""tests/dual-issue/check.py UAM: compiles every shader of tests/dual-issue and checks that no instruction is
dual-issued with the next (a scheduling field with a stall of 0 and the yield bit, the pair uam's Maxwell
dual-issue scheduler made). Exits 1 naming each shader that has a pair."""
import pathlib
import struct
import subprocess
import sys
import tempfile

STAGES = {'.vert': 'vert', '.frag': 'frag', '.comp': 'comp', '.geom': 'geom', '.tesc': 'tess_ctrl', '.tese': 'tess_eval'}
COMPUTE = 5


def pairs(data):
    _magic, _hsz, control_sz, code_sz, programs_off, count = struct.unpack_from('<6I', data, 0)
    found = 0
    for i in range(count):
        typ, entry, _gprs, cb_off, cb_sz = struct.unpack_from('<5I', data, programs_off + 0x40 * i)
        start = control_sz + entry + (0 if typ == COMPUTE else 0x50)
        code = data[start:control_sz + (cb_off if cb_sz else code_sz)]
        for g in range(0, len(code) - 31, 32):
            ctrl = struct.unpack_from('<Q', code, g)[0]
            found += sum(1 for k in range(3) if ((ctrl >> (21 * k)) & 0x1F) == 0x10)
    return found


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        for shader in sorted(pathlib.Path(__file__).parent.iterdir()):
            if shader.suffix not in STAGES:
                continue
            out = pathlib.Path(tmp) / (shader.name + '.dksh')
            run = subprocess.run([sys.argv[1], '-s', STAGES[shader.suffix], '-o', str(out), str(shader)],
                                 capture_output=True, text=True)
            if run.returncode:
                print(f'{shader.name}: uam failed: {run.stderr.strip()}')
                failed = True
                continue
            n = pairs(out.read_bytes())
            print(f'{shader.name}: ' + (f'{n} dual-issued instructions' if n else 'ok, none dual-issued'))
            failed |= n > 0
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

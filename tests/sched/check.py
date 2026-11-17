#!/usr/bin/env python3
"""tests/sched/check.py UAM [RUNS]: compiles every shader of tests/sched RUNS times (8 by default, address
randomization left on) and checks two things of uam's scheduling words:

- the output is the same in every run;
- no instruction that sets a dependency barrier lets an instruction that waits on it issue one cycle later or less:
  a barrier becomes active one cycle after the instruction that sets it (SchedDataCalculatorGM107::setDelay), so
  such a wait passes before the result is there.

Exits 1 naming each shader and what failed."""
import hashlib
import pathlib
import struct
import subprocess
import sys
import tempfile

STAGES = {'.vert': 'vert', '.frag': 'frag', '.comp': 'comp', '.geom': 'geom', '.tesc': 'tess_ctrl', '.tese': 'tess_eval'}
COMPUTE = 5


def programs(data):
    _magic, _hsz, control_sz, code_sz, programs_off, count = struct.unpack_from('<6I', data, 0)
    for i in range(count):
        typ, entry, _gprs, cb_off, cb_sz = struct.unpack_from('<5I', data, programs_off + 0x40 * i)
        start = control_sz + entry + (0 if typ == COMPUTE else 0x50)
        yield data[start:control_sz + (cb_off if cb_sz else code_sz)]


def late_waits(data):
    """instructions whose next one waits on a barrier they set with a stall of 0 or 1"""
    found = []
    for code in programs(data):
        fields, insns = [], []
        for g in range(0, len(code) - 31, 32):
            ctrl, a, b, c = struct.unpack_from('<4Q', code, g)
            fields += [(ctrl >> (21 * k)) & 0x1FFFFF for k in range(3)]
            insns += [a, b, c]
        for k in range(len(fields) - 1):
            if not insns[k] or not insns[k + 1]:
                continue
            f, wait = fields[k], (fields[k + 1] >> 11) & 0x3F
            bars = [b for b in ((f >> 5) & 7, (f >> 8) & 7) if b != 7]
            if (f & 0xF) <= 1 and any(wait & (1 << b) for b in bars):
                found.append(k)
    return found


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    uam, runs = sys.argv[1], int(sys.argv[2]) if len(sys.argv) == 3 else 8
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        for shader in sorted(pathlib.Path(__file__).parent.iterdir()):
            if shader.suffix not in STAGES:
                continue
            outputs = []
            for r in range(runs):
                out = pathlib.Path(tmp) / f'{shader.name}.{r}.dksh'
                run = subprocess.run([uam, '-s', STAGES[shader.suffix], '-o', str(out), str(shader)],
                                     capture_output=True, text=True)
                if run.returncode:
                    print(f'{shader.name}: uam failed: {run.stderr.strip()}')
                    failed = True
                    break
                outputs.append(out.read_bytes())
            else:
                distinct = len({hashlib.sha256(o).digest() for o in outputs})
                waits = sorted({k for o in outputs for k in late_waits(o)})
                if distinct > 1:
                    print(f'{shader.name}: {distinct} different outputs in {runs} runs')
                if waits:
                    print(f'{shader.name}: instructions {waits} set a barrier the next instruction waits on, '
                          'with a stall of 1 or less')
                if distinct > 1 or waits:
                    failed = True
                else:
                    print(f'{shader.name}: ok, {runs} runs')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

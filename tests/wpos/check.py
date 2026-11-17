#!/usr/bin/env python3
"""tests/wpos/check.py UAM: compiles tests/wpos/derivatives.frag and checks the program's constant buffer, where uam
puts STATE_FB_WPOS_Y_TRANSFORM: its first word, which dFdy, fwidth and interpolateAtOffset multiply by, must be 1.0,
which keeps the derivative the hardware computes. Left unresolved it is 0.0, and dFdy returns 0. Exits 1 with the
words it found."""
import pathlib
import struct
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    shader = pathlib.Path(__file__).parent / 'derivatives.frag'
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / 'derivatives.dksh'
        run = subprocess.run([sys.argv[1], '-s', 'frag', '-o', str(out), str(shader)], capture_output=True, text=True)
        if run.returncode:
            raise SystemExit(f'derivatives.frag: uam failed: {run.stderr.strip()}')
        data = out.read_bytes()
    _magic, _hsz, control_sz, _code_sz, programs_off, _count = struct.unpack_from('<6I', data, 0)
    _typ, _entry, _gprs, cb_off, cb_sz = struct.unpack_from('<5I', data, programs_off)
    words = struct.unpack_from(f'<{cb_sz // 4}f', data, control_sz + cb_off)
    if not words or words[0] != 1.0:
        print(f'derivatives.frag: the transform\'s first word is {words[0] if words else "missing"}, wants 1.0 '
              f'(constant buffer {list(words)})')
        sys.exit(1)
    print(f'derivatives.frag: ok, constant buffer {list(words)}')


if __name__ == '__main__':
    main()

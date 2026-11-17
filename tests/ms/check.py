#!/usr/bin/env python3
"""tests/ms/check.py UAM ENVYDIS: compiles tests/ms/handle_ms.frag, disassembles it with envytools' envydis and
checks that the multisample TLD's Rb, where the hardware reads a bindless handle, is the register the handle was
loaded into from the uniform block, and not the sample index. Exits 1 with the instructions that disagree."""
import pathlib
import re
import subprocess
import sys
import tempfile


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    uam, envydis = sys.argv[1:]
    shader = pathlib.Path(__file__).parent / 'handle_ms.frag'
    with tempfile.TemporaryDirectory() as tmp:
        raw = pathlib.Path(tmp) / 'handle_ms.raw'
        run = subprocess.run([uam, '-s', 'frag', '-o', str(pathlib.Path(tmp) / 'handle_ms.dksh'), '-r', str(raw),
                              str(shader)], capture_output=True, text=True)
        if run.returncode:
            raise SystemExit(f'handle_ms.frag: uam failed: {run.stderr.strip()}')
        sass = subprocess.run([envydis, '-m', 'gm107', '-i', '-n'], stdin=raw.open('rb'), capture_output=True,
                              text=True, check=True).stdout.splitlines()
    loads = [l for l in sass if re.search(r'\b(?:mov|ld b32) \$r\d+ c\d+\[', l)]
    tlds = [l for l in sass if re.search(r'\btld\b.*\bms\b', l)]
    if len(loads) != 1 or len(tlds) != 1:
        raise SystemExit(f'handle_ms.frag: wants one constant load and one multisample tld, got {loads} and {tlds}')
    handle = re.search(r'(?:mov|ld b32) (\$r\d+)', loads[0]).group(1)
    regs = re.findall(r'\$r\d+', tlds[0].split('tld', 1)[1])
    rb = regs[2] if len(regs) > 2 else None  # destination, Ra, Rb
    if rb != handle:
        print(f'handle_ms.frag: the handle is in {handle} and the tld reads Rb {rb}:\n  {loads[0]}\n  {tlds[0]}')
        sys.exit(1)
    print(f'handle_ms.frag: ok, the tld reads the handle from {rb}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""tests/nvn/check.py UAM ENVYDIS: compiles tests/nvn/buffers.comp and buffers.frag with and without --nvn,
disassembles them with envytools' envydis, and checks where each reads the driver's constant buffers. With --nvn a
compute program reads its storage buffer's descriptor at 0x310 of bank 0 and a fragment program at 0x510 (the tables
NVN's driver writes), both read their uniform block from bank 3 (NVN's slot 0), and neither reads bank 2 (NVN's
texture handles); without it they read deko3d's places: the compute program's descriptor at 0x140 and the uniform
block from bank 2. Exits 1 with what disagrees."""
import pathlib
import re
import subprocess
import sys
import tempfile

CONSTANT = re.compile(r'\bc(\d+)\[(?:\$r\d+\s*\+\s*)?(0x[0-9a-f]+)\]')


def reads(uam, envydis, stage, nvn, tmp):
    """(bank, offset) of every constant buffer read the program's instructions name"""
    shader = pathlib.Path(__file__).parent / f'buffers.{stage}'
    raw = pathlib.Path(tmp) / f'{stage}.raw'
    run = subprocess.run([uam] + (['--nvn'] if nvn else []) + ['-s', stage, '-o', str(pathlib.Path(tmp) / 'x.dksh'),
                          '-r', str(raw), str(shader)], capture_output=True, text=True)
    # uam answers an option it does not know with its usage and status 0, writing nothing
    if run.returncode or not raw.exists():
        said = (run.stderr.strip() or run.stdout.strip()).splitlines()
        raise SystemExit(f'buffers.{stage}: uam gave status {run.returncode} and no code: {said[0] if said else ""}')
    sass = subprocess.run([envydis, '-m', 'gm107', '-i', '-n'], stdin=raw.open('rb'), capture_output=True,
                          text=True, check=True).stdout
    return {(int(b), int(o, 16)) for b, o in CONSTANT.findall(sass)}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    uam, envydis = sys.argv[1:]
    wrong = []
    with tempfile.TemporaryDirectory() as tmp:
        for stage, table in (('comp', (0x200, 0x410)), ('frag', (0x510, 0x610))):
            got = reads(uam, envydis, stage, True, tmp)
            descriptor = 0x310 if stage == 'comp' else 0x510
            if (0, descriptor) not in got:
                wrong.append(f'--nvn {stage}: no read of its storage buffer at c0[{descriptor:#x}]: {sorted(got)}')
            outside = sorted((b, o) for b, o in got if (b == 0 and not table[0] <= o < table[1]) or b == 2)
            if outside:
                wrong.append(f'--nvn {stage}: reads outside NVN\'s tables or of bank 2: {outside}')
            if not any(b == 3 for b, _ in got):
                wrong.append(f'--nvn {stage}: no read of bank 3, NVN\'s uniform buffer slot 0: {sorted(got)}')
        plain = reads(uam, envydis, 'comp', False, tmp)
        if (0, 0x140) not in plain or not any(b == 2 for b, _ in plain):
            wrong.append(f'comp without --nvn: not deko3d\'s c0[0x140] and bank 2: {sorted(plain)}')
    if wrong:
        print('\n'.join(wrong))
        sys.exit(1)
    print('buffers.comp and buffers.frag: ok, --nvn reads NVN\'s tables and bank 3, and without it deko3d\'s places')


if __name__ == '__main__':
    main()

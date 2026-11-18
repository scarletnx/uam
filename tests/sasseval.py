#!/usr/bin/env python3
"""Runs a test shader's Maxwell code, one thread at a time, and checks the words it stores.

    sasseval.py SHADER SASS

SHADER is a compute shader of tests/ubo/ and SASS the envydis text of the code uam made of it (envydis -m gm107 -i -n
on uam's -r output). Thread i runs with $tidx = i, for the 64 threads of the shader's block. Word w of uniform block 0
holds U(w), 0x1000 + w or what the shader's "// ubo:" line says, and word w of storage buffer 1 holds S(w),
0x2000 + w; the shader's "// expect:" line is a Python expression of U and S giving each word of storage buffer 0 the
value it must hold.

An instruction this file does not know stops the run with its text, as do a read of the driver block (c0) other than
the storage buffers' addresses, an access outside the buffers and a register used before any write, unless it only
feeds a select that does not pick it. Exit 0 when the shader stores exactly the words it should, 1 when it does not.
"""

import re
import sys

M32 = 0xFFFFFFFF
THREADS = 64
# Storage buffer n's address is at c0[0x140 + 16 * n] in deko3d's compute driver block.
SSBO_BASE = (0x1_0000_0000, 0x2_0000_0000)
SSBO_SIZE = 4096

LINE = re.compile(r"^[0-9a-f]+: [0-9a-f]+ [0-9a-f]+ +(.*)$")
CBUF = re.compile(r"^c(\d+)\[(\$r\d+)?(?:\+?(-?0x[0-9a-f]+))?\]$")
GMEM = re.compile(r"^ncg\[(\$r\d+)(?:\+(0x[0-9a-f]+))?\]$")
IMM = re.compile(r"^-?0x[0-9a-f]+$")


class Stop(Exception):
    pass


class Undefined:
    """What a register holds before any write. Arithmetic on it gives it back; comparing or storing it stops."""

    def _same(self, *_):
        return self

    __and__ = __rand__ = __or__ = __ror__ = __xor__ = __rxor__ = _same
    __add__ = __radd__ = __lshift__ = __rlshift__ = __rshift__ = __rrshift__ = _same

    def __bool__(self):
        raise Stop("a register used before any write decides a result")


UNDEFINED = Undefined()


def ssbo_word(addr, text):
    for n, base in enumerate(SSBO_BASE):
        off = addr - base
        if 0 <= off < SSBO_SIZE and off % 4 == 0:
            return n, off // 4
    raise Stop(f"an access at {addr:#x}, not a word of a storage buffer: {text}")


def gmem_addr(val, known, tok, text):
    m = GMEM.match(tok)
    if not m:
        raise Stop(f"global address {tok}: {text}")
    lo, hi = m.group(1), f"$r{int(m.group(1)[2:]) + 1}"
    return (known(val(hi))[0] << 32 | known(val(lo))[0]) + int(m.group(2) or "0", 16)


def run(code, ubo, ssbo1, tid):
    regs, preds, stores = {}, {}, {}
    carry = 0
    text = ""

    def known(*values):
        if any(v is UNDEFINED for v in values):
            raise Stop(f"a register used before any write: {text}")
        return values

    def val(tok):
        if tok.startswith("$r"):
            return regs.get(tok, UNDEFINED)
        if tok == "$tidx":
            return tid
        if IMM.match(tok):
            return int(tok, 16) & M32
        m = CBUF.match(tok)
        if not m:
            raise Stop(f"operand {tok} in: {text}")
        bank, reg, off = int(m.group(1)), m.group(2), m.group(3)
        (addr,) = known((val(reg) if reg else 0) + (int(off, 16) if off else 0))
        if bank == 0:
            n, part = divmod(addr - 0x140, 16)
            if addr >= 0x140 and n < len(SSBO_BASE) and part in (0, 4):
                return SSBO_BASE[n] >> (8 * part) & M32
            raise Stop(f"read of c0[{addr:#x}]: {text}")
        if bank != 2 or addr % 4:
            raise Stop(f"read of c{bank}[{addr:#x}], not a word of uniform block 0 (c2): {text}")
        return ubo(addr // 4)

    for text in code:
        t = text.split()
        if t[0] == "not" and t[1].startswith("$p"):
            if preds.get(t[1], False):
                continue
            t = t[2:]
        elif t[0].startswith("$p"):
            if not preds.get(t[0], False):
                continue
            t = t[1:]
        op = t[0]
        if op == "exit":
            return stores
        if op == "nop":
            continue
        if op in ("mov", "mov32i") and (len(t) == 3 or len(t) == 4 and t[3] == "0xf"):
            regs[t[1]] = val(t[2])
        elif op == "shl" and len(t) == 4:
            regs[t[1]] = (val(t[2]) << known(val(t[3]))[0] % 32) & M32
        elif op == "shr" and t[1] == "u32" and len(t) == 5:
            regs[t[2]] = val(t[3]) >> known(val(t[4]))[0] % 32
        elif op == "lop" and t[1] in ("and", "or", "xor") and t[2] == "0x1" and len(t) == 6:
            a, b = val(t[4]), val(t[5])
            regs[t[3]] = {"and": a & b, "or": a | b, "xor": a ^ b}[t[1]]
        elif op == "iscadd" and len(t) == 5:
            regs[t[1]] = ((val(t[2]) << known(val(t[4]))[0]) + val(t[3])) & M32
        elif op == "bfe" and t[1] == "u32" and len(t) == 5:
            (spec,) = known(val(t[4]))
            regs[t[2]] = (val(t[3]) >> (spec & 0xFF)) & ((1 << (spec >> 8 & 0xFF)) - 1)
        elif op == "imnmx" and t[1] == "u32" and len(t) == 6 and t[5] == "0x1":
            regs[t[2]] = min(known(val(t[3]), val(t[4])))
        elif op == "iset" and t[1] in ("eq", "ne") and t[2:4] == ["u32", "and"] and len(t) == 8 and t[7] == "0x1":
            a, b = known(val(t[5]), val(t[6]))
            regs[t[4]] = M32 if (a == b) == (t[1] == "eq") else 0
        elif (
            op == "isetp"
            and t[1] in ("eq", "ne")
            and t[2:4] == ["u32", "and"]
            and len(t) == 9
            and t[5] == t[8] == "0x1"
        ):
            a, b = known(val(t[6]), val(t[7]))
            preds[t[4]] = (a == b) == (t[1] == "eq")
        elif op == "icmp" and t[1:3] == ["ne", "u32"] and len(t) == 7:
            (c,) = known(val(t[6]))
            regs[t[3]] = val(t[4]) if c != 0 else val(t[5])
        elif op == "ld" and t[1] == "b32" and len(t) == 4:
            regs[t[2]] = val(t[3])
        elif op == "iadd" and t[1] == "cc" and len(t) == 5:
            s = known(val(t[3]))[0] + known(val(t[4]))[0]
            carry, regs[t[2]] = s >> 32, s & M32
        elif op == "iadd" and t[1] == "x" and len(t) == 5:
            regs[t[2]] = (val(t[3]) + val(t[4]) + carry) & M32
        elif op == "iadd" and len(t) == 4:
            regs[t[1]] = (val(t[2]) + val(t[3])) & M32
        elif op == "ldg" and t[1:3] == ["e", "b32"] and len(t) == 5:
            n, w = ssbo_word(gmem_addr(val, known, t[4], text), text)
            if n != 1:
                raise Stop(f"a load from storage buffer {n}, which only takes stores: {text}")
            regs[t[3]] = ssbo1(w)
        elif op == "stg" and t[1:3] == ["e", "b32"] and len(t) == 5:
            n, w = ssbo_word(gmem_addr(val, known, t[3], text), text)
            if n != 0:
                raise Stop(f"a store to storage buffer {n}, which only takes loads: {text}")
            stores[w] = known(val(t[4]))[0]
        else:
            raise Stop(f"an instruction this file does not run: {text}")
    raise Stop("the code ends without exit")


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    shader, sass = sys.argv[1:]
    with open(shader) as f:
        source = f.read()
    with open(sass) as f:
        listing = f.read().splitlines()
    ubo_rule = re.search(r"^// ubo: (.+)$", source, re.MULTILINE)
    expect_rule = re.search(r"^// expect: (.+)$", source, re.MULTILINE)
    if not expect_rule:
        raise SystemExit(f"{shader} has no '// expect:' line")
    ubo = eval(f"lambda w: {ubo_rule.group(1) if ubo_rule else '0x1000 + w'}")
    ssbo1 = lambda w: 0x2000 + w
    want = eval(expect_rule.group(1), {"U": ubo, "S": ssbo1, "min": min, "range": range})
    code = [m.group(1) for m in map(LINE.match, listing) if m and not m.group(1).startswith("sched")]
    got = {}
    name = shader.rsplit("/", 1)[-1]
    try:
        for tid in range(THREADS):
            for w, v in run(code, ubo, ssbo1, tid).items():
                if w in got:
                    raise Stop(f"word {w} stored by thread {got[w][0]} and by this one")
                got[w] = (tid, v)
    except Stop as e:
        print(f"{name}: stopped in thread {tid}, {e}")
        sys.exit(1)
    got = {w: v for w, (_, v) in got.items()}
    bad = [w for w in sorted(set(want) | set(got)) if got.get(w) != want.get(w)]
    if not bad:
        print(f"{name}: ok, {len(want)} words")
        sys.exit(0)
    shown = []
    for w in bad[:4]:
        if w not in got:
            shown.append(f"word {w} never stored (wants {want[w]:#x})")
        elif w not in want:
            shown.append(f"word {w} stored as {got[w]:#x}, wants none")
        else:
            shown.append(f"word {w} is {got[w]:#x}, wants {want[w]:#x}")
    print(f"{name}: WRONG in {len(bad)} of {len(want)} words: {'; '.join(shown)}")
    sys.exit(1)


if __name__ == "__main__":
    main()

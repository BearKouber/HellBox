"""读 LuaJIT 2.0 编译好的脚本（游戏里的原版 bytecode，去掉调试信息的那种），给 eight_players.py 找要改的位置用。

只读不写：返回每个函数（proto）的指令起点和数字常量所在的字节位置，改字节由调用方做。
"""
OPS = ("ISLT ISGE ISLE ISGT ISEQV ISNEV ISEQS ISNES ISEQN ISNEN ISEQP ISNEP ISTC ISFC IST ISF "
       "MOV NOT UNM LEN ADDVN SUBVN MULVN DIVVN MODVN ADDNV SUBNV MULNV DIVNV MODNV ADDVV SUBVV MULVV DIVVV MODVV "
       "POW CAT KSTR KCDATA KSHORT KNUM KPRI KNIL UGET USETV USETS USETN USETP UCLO FNEW TNEW TDUP GGET GSET "
       "TGETV TGETS TGETB TSETV TSETS TSETB TSETM CALLM CALL CALLMT CALLT ITERC ITERN VARG ISNEXT RETM RET RET0 RET1 "
       "FORI JFORI FORL IFORL JFORL ITERL IITERL JITERL LOOP ILOOP JLOOP JMP FUNCF IFUNCF JFUNCF FUNCV IFUNCV JFUNCV FUNCC FUNCCW").split()
OP = {n: i for i, n in enumerate(OPS)}


def _uleb(b, o):
    v = s = 0
    while True:
        x = b[o]
        o += 1
        v |= (x & 0x7F) << s
        s += 7
        if x < 0x80:
            return v, o


def _uleb33(b, o):
    x = b[o] >> 1
    if b[o] < 0x80:
        return x, o + 1
    x &= 0x3F
    s = 6
    o += 1
    while True:
        c = b[o]
        o += 1
        x |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return x, o


def _skip_tabk(b, o):
    t, o = _uleb(b, o)
    if t >= 5:
        return o + t - 5
    if t == 3:
        return _uleb(b, o)[1]
    if t == 4:
        return _uleb(b, _uleb(b, o)[1])[1]
    return o


class Proto:
    """bc_off：第一条指令的字节位置；nbc：指令条数；kgc：字符串 / 表常量（按文件里的顺序，字符串是 str）；
    kn：数字常量 [(值, 字节位置, 是不是整数)]。"""


def protos(bc):
    """按文件里的顺序（先子函数后父函数）列出所有函数。"""
    if bc[:3] != b"\x1bLJ":
        raise ValueError("不是 LuaJIT 脚本")
    o = 4
    flags, o = _uleb(bc, o)
    if not flags & 2:
        raise ValueError("脚本带调试信息，不是游戏里的那种")
    out = []
    while True:
        ln, o = _uleb(bc, o)
        if ln == 0:
            return out
        p = Proto()
        p.nuv = bc[o + 3]
        q = o + 4
        nkgc, q = _uleb(bc, q)
        nkn, q = _uleb(bc, q)
        p.nbc, q = _uleb(bc, q)
        p.bc_off = q
        q += 4 * p.nbc + 2 * p.nuv
        p.kgc = []
        for _ in range(nkgc):
            t, q = _uleb(bc, q)
            if t >= 5:
                p.kgc.append(bc[q:q + t - 5].decode("latin1"))
                q += t - 5
            elif t == 1:
                na, q = _uleb(bc, q)
                nh, q = _uleb(bc, q)
                for _ in range(na + 2 * nh):
                    q = _skip_tabk(bc, q)
                p.kgc.append(("table",))
            elif t in (2, 3):
                q = _uleb(bc, _uleb(bc, q)[1])[1]
                p.kgc.append(("int64",))
            elif t == 4:
                for _ in range(4):
                    q = _uleb(bc, q)[1]
                p.kgc.append(("complex",))
            else:
                p.kgc.append(("child",))
        p.kn = []
        for _ in range(nkn):
            at = q
            isnum = bc[q] & 1
            lo, q = _uleb33(bc, q)
            if isnum:
                _hi, q = _uleb(bc, q)
                p.kn.append((None, at, False))
            else:
                p.kn.append((lo if lo < 2 ** 31 else lo - 2 ** 32, at, True))
        out.append(p)
        o += ln


def ins(bc, p, k):
    """第 k 条指令：(字节位置, 指令名, A, D)。"""
    at = p.bc_off + 4 * k
    op = bc[at]
    return at, OPS[op] if op < len(OPS) else "?", bc[at + 1], bc[at + 2] | (bc[at + 3] << 8)


def kgc_str(p, d):
    """GGET / TDUP 这类指令的 D 指向的常量（从常量表末尾往前数）。"""
    return p.kgc[len(p.kgc) - 1 - d]


def kgc_index(p, text):
    """字符串常量 text 对应的 D 值；没有返回 None。"""
    for i, s in enumerate(p.kgc):
        if s == text:
            return len(p.kgc) - 1 - i
    return None

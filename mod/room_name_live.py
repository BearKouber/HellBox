"""热改名字：往游戏里改名 mod 的信箱表写新名字（表布局见 src/room_name.lua、src/p2_name.lua 文件头，三边要一致）。

    live_set(name)                  # 房间名
    live_set(name, magic=MAGIC_SELF)  # 自己（主手柄）的名字
    live_set(name, magic=MAGIC_P2)  # 本地 2P 名字
    live_set(build.front_mail(), magic=MAGIC_FRONT)  # 战线开关 + 报复概率 "f=1;g=100"（旧格式 "1" / "" 只管战线）
    live_set("", magic=MAGIC_REFRESH)       # 刷新星球（下次打开战役地图生效）
    live_set("on=1;seed=71000046", magic=MAGIC_TEST)  # 自动测试开关（见 src/ai_test.lua 文件头；ai/test_switch.py 包了一层）
    # 游戏没开 / mod 没装（找不到表）抛 RuntimeError；mod 几秒内没回应也抛
"""
import ctypes
import struct
import time
from ctypes import wintypes

MAGIC = struct.pack("<4d", 27182818.5, -577215.75, 1618.03125, 549755813888.375)  # room_name.lua
MAGIC_SELF = struct.pack("<4d", 16777216.5, -299792.375, 3141.5625, 17179869184.25)  # self_name.lua
MAGIC_P2 = struct.pack("<4d", 31415926.5, -141421.25, 2236.0625, 274877906944.625)  # p2_name.lua
MAGIC_FRONT = struct.pack("<4d", 16180339.5, -271828.25, 1414.0625, 137438953472.875)  # front_unlock.lua（"f=1;g=100"，见文件头）
MAGIC_REFRESH = struct.pack("<4d", 44721359.5, -301029.875, 2645.75, 34359738368.125)  # planet_refresh.lua（内容不看）
MAGIC_RESULTS = struct.pack("<4d", 72187331.5, -141551.875, 4217.5625, 17179869184.875)
MAGIC_PROFILE = struct.pack("<4d", 27644437.5, -693147.125, 2756.0625, 8589934592.75)  # profile_tool.lua（命令 + 状态，见 live_read）
MAGIC_TEST = struct.pack("<4d", 57721566.5, -662607.125, 1732.0625, 68719476736.375)  # ai_test.lua（命令 "on=1;seed=…" / "on=0" / "abort=1"）
MAGIC_SPAWN = struct.pack("<4d", 24494897.5, -173205.375, 2071.875, 137438953472.625)  # spawn_rules.lua（出怪设置，见 src/spawn_rules.lua 文件头）
MAGIC_PARAMS = struct.pack("<4d", 26457513.5, -793700.875, 1905.25, 274877906944.125)  # enemy_params.lua（"set=名.路径=值,…" / "reset"）
MAGIC_DRILL = struct.pack("<4d", 33166247.5, -223606.625, 2449.4375, 68719476736.875)  # ai_drill.lua（出怪练习设置，2026-11-13）
B0 = 9
# 信箱表布局：(VERSION, 最多几个字节)。三个名字表 2026-11-08 起是 VERSION 3、8192 字节（名字长度不限，房间名受 Steam 8192 字节限制）。
# 注意：找表时不再要求版本号完全相等（见 _table），这里只留个记录；表大小变了才必须同步。
NAME_MAX_BYTES = 8192
CMD_MAX_BYTES = 4096
LAYOUT = {MAGIC: (3, NAME_MAX_BYTES), MAGIC_SELF: (3, NAME_MAX_BYTES), MAGIC_P2: (3, NAME_MAX_BYTES),
          MAGIC_RESULTS: (1, 1), MAGIC_REFRESH: (3, 256), MAGIC_PROFILE: (1, 256), MAGIC_SPAWN: (4, CMD_MAX_BYTES), MAGIC_PARAMS: (2, CMD_MAX_BYTES),
          MAGIC_DRILL: (1, 512)}
# 有"状态"区的表（游戏写、窗口读）：魔数 -> (状态区起点格号（从 1 数）, 最多几个字节)。见 live_read
# 2026-11-15：profile_tool 状态区 8192 → 16384（加了战略配备）；读的时候只看字节数不超过这个，旧版 MOD 也能读
OUT_LAYOUT = {MAGIC_RESULTS: (10, 4096), MAGIC_REFRESH: (B0 + 256, 128), MAGIC_PROFILE: (B0 + 256, 16384), MAGIC_SPAWN: (B0 + CMD_MAX_BYTES, 8192),
              MAGIC_PARAMS: (B0 + CMD_MAX_BYTES, CMD_MAX_BYTES)}
DEFAULT_LAYOUT = (2, 256)

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}


class MemoryRegion(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("allocation", ctypes.c_void_p),
                ("allocation_protect", wintypes.DWORD), ("partition_id", wintypes.WORD),
                ("size", ctypes.c_size_t), ("state", wintypes.DWORD),
                ("protect", wintypes.DWORD), ("kind", wintypes.DWORD)]


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MemoryRegion), ctypes.c_size_t]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.WriteProcessMemory.restype = ctypes.c_int
k32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]

_cache = {}  # (pid, 魔数) -> 表地址（同一次游戏里不用每次都扫一遍内存）


def find_pid(name="helldivers.exe"):
    import subprocess
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"], capture_output=True,
                       text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in r.stdout.splitlines():
        cells = [c.strip('"') for c in line.split('","')]
        if len(cells) > 1 and cells[0].lower() == name:
            return int(cells[1])
    return None


def _read(h, addr, n):
    buf = ctypes.create_string_buffer(n * 8)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, addr, buf, n * 8, ctypes.byref(got)) or got.value != n * 8:
        return None
    return list(memoryview(buf.raw).cast("d"))


def _write(h, addr, values):
    data = struct.pack(f"<{len(values)}d", *values)
    got = ctypes.c_size_t()
    if not k32.WriteProcessMemory(h, addr, data, len(data), ctypes.byref(got)) or got.value != len(data):
        raise OSError(ctypes.get_last_error(), "写不进游戏内存")


def _scan(handle, magic):
    """Yield aligned LuaJIT mailbox addresses in the low 4 GiB."""
    region = MemoryRegion()
    address = 0x10000
    limit = 0x100000000
    chunk = 16 << 20
    while address < limit and k32.VirtualQueryEx(handle, address, ctypes.byref(region), ctypes.sizeof(region)):
        base = region.base or 0
        size = region.size
        if region.state == MEM_COMMIT and region.protect & 0xFF in READABLE and not region.protect & PAGE_GUARD:
            for offset in range(0, min(size, limit - base), chunk):
                count = min(chunk + len(magic), size - offset, limit - base - offset)
                buffer = ctypes.create_string_buffer(count)
                got = ctypes.c_size_t()
                if k32.ReadProcessMemory(handle, base + offset, buffer, count, ctypes.byref(got)):
                    data = buffer.raw[:got.value]
                    index = data.find(magic)
                    while index >= 0:
                        candidate = base + offset + index
                        if candidate % 8 == 0:
                            yield candidate
                        index = data.find(magic, index + 1)
        address = base + size


def _table(h, pid, magic):
    """找信箱表，返回 (地址, 表头 8 格)。魔数是主要依据；版本号只要求是正数，mod 升级 VERSION 后不会认不出来。"""
    key = (pid, magic)
    addrs = [_cache[key]] if key in _cache else []
    for scan in (False, True):
        if scan:
            addrs = _scan(h, magic)
        for a in addrs:
            v = _read(h, a, 8)
            if v and struct.pack("<4d", *v[:4]) == magic and 1 <= v[4] <= 10000:
                _cache[key] = a
                return a, v
    _cache.pop(key, None)
    return None, None


def _open(pid, write):
    pid = pid or find_pid()
    if not pid:
        raise RuntimeError("游戏没在运行。")
    access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | (PROCESS_VM_WRITE | PROCESS_VM_OPERATION if write else 0)
    h = k32.OpenProcess(access, False, pid)
    if not h:
        raise OSError(ctypes.get_last_error(), "打不开游戏进程")
    return pid, h


def live_read(magic=MAGIC_PROFILE, pid=None, tries=5):
    """读游戏写的状态文字（OUT_LAYOUT 里的表）。状态区：第 1 格序号（写完最后加 1）、第 2 格字节数、之后是 UTF-8 字节。
    读前读后序号一样才算数（防止读到写了一半的）。返回 (序号, 文字)；游戏没开 / mod 没装抛 RuntimeError。"""
    out0, max_bytes = OUT_LAYOUT[magic]
    pid, h = _open(pid, write=False)
    try:
        addr, header = _table(h, pid, magic)
        if addr is None or magic == MAGIC_REFRESH and header[4] < 3:
            raise RuntimeError("游戏里没找到这个 mod（可能装的是旧版本：关掉游戏在 HellBox 里装一次 mod）。")
        base = addr + (out0 - 1) * 8
        for _ in range(tries):
            head = _read(h, base, 2)
            if not head:
                break
            seq, n = head
            n = int(n)
            if not 0 <= n <= max_bytes:
                time.sleep(0.02)
                continue
            body = _read(h, base + 16, n) if n else []
            again = _read(h, base, 1)
            if body is not None and again and again[0] == seq:
                return seq, bytes(int(b) & 0xFF for b in body).decode("utf-8", "replace")
            time.sleep(0.02)
        raise RuntimeError("读游戏状态失败，稍后再试。")
    finally:
        k32.CloseHandle(h)


def live_set(name, timeout=3.0, pid=None, magic=MAGIC):
    data = name.encode("utf-8")
    max_bytes = LAYOUT.get(magic, DEFAULT_LAYOUT)[1]
    if len(data) > max_bytes:
        raise ValueError(f"太长了（最多 {max_bytes} 字节）。")
    pid = pid or find_pid()
    if not pid:
        raise RuntimeError("游戏没在运行。")
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION,
                        False, pid)
    if not h:
        raise OSError(ctypes.get_last_error(), "打不开游戏进程")
    try:
        addr, v = _table(h, pid, magic)
        if addr is None:
            raise RuntimeError("游戏里没找到这个 mod（可能装的是旧版本：关掉游戏再点一次）。")
        seq = v[5] + 1
        # 先写名字和长度，最后写请求号，mod 看到请求号变了才读
        _write(h, addr + (B0 - 1) * 8, list(data))
        _write(h, addr + 7 * 8, [len(data)])
        _write(h, addr + 5 * 8, [seq])
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = _read(h, addr, 8)
            if v and v[6] == seq:
                return
            time.sleep(0.05)
        raise RuntimeError("mod 没有回应（游戏可能卡在加载，或者窗口最小化暂停了），稍后再试。")
    finally:
        k32.CloseHandle(h)

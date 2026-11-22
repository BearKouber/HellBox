r"""把分屏（HalfSugar 的 CameraCTRL）接进游戏的启动脚本：Python 版，代替以前发行包带的 CameraCTRL-bridge.exe。

2026-11-21 HD1-037（用户定：为过 N 网病毒扫描，发行包不再带分屏 exe；那个 exe 被 3 家杀毒软件误报）。
逐行照搬 CameraCTRL 依赖的 BridgeCore（camera-src/BridgeCore/src/install.rs 的 prepare / patch_raw /
patch_chunk / boot_record / validate_bytecode，boot.rs 的启动脚本校验），作者同意收进 HellBox、同意开源。

做的事：游戏启动脚本（核心包里的 BOOT_ID 资源，一段 stripped LuaJIT 2.0 字节码）末尾的 RET 之前，
插一句 pcall(分屏模块)，分屏模块的字节码（mod/camera/runtime.luac，半糖的 bridge/compile.py 编的）
作为子函数接在启动函数前面。原来的启动逻辑、所有常量编号都不动。
接在「解压后的整包数据」上做（build.py 压缩之前），和 exe 的输出解压后逐字节一样（见 HD1-037 任务记录）。
"""
import hashlib
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
CAMERA_LUAC = os.path.join(HERE, "camera", "runtime.luac")
# 分屏模块字节码的 sha256（半糖 runtime.sha256 第二行；换了新版分屏要一起改）
CAMERA_LUAC_SHA = "2dff93e508cebed478938b2d4d91560f070479ac6be5a70ddab8aae9d5299e68"
# 原版启动脚本的 sha256（boot.rs VANILLA_SCRIPT_SHA）：不是这个版本就不接，免得接坏
VANILLA_SCRIPT_SHA = "8274d9e67af56be5f07bbff994ba4e7366599e439014d665c092c02a9f6ec624"
BOOT_ID = bytes([0xe2, 0x17, 0xd1, 0x2c, 0xfa, 0x8d, 0x4e, 0xa1, 0x81, 0xdc, 0xbd, 0x8a, 0x61, 0x8a, 0x04, 0x37])
LJ_HEADER = bytes([27, 76, 74, 1, 2])  # LuaJIT 2.0 dump v1，stripped


class CameraError(RuntimeError):
    pass


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _u32(b, p):
    if p + 4 > len(b):
        raise CameraError("截断的资源包")
    return struct.unpack_from("<I", b, p)[0]


def _uleb(b, p):
    n = 0
    for shift in range(0, 35, 7):
        if p >= len(b):
            raise CameraError("截断的字节码")
        v = b[p]
        p += 1
        n |= (v & 127) << shift
        if v < 128:
            return n, p
    raise CameraError("无效 ULEB128")


def _put_uleb(out, n):
    while True:
        v = n & 127
        n >>= 7
        out.append(v | (128 if n else 0))
        if not n:
            break


def _ins(op, a, d):
    return bytes([op, a, d & 0xFF, (d >> 8) & 0xFF])


def validate_bytecode(b):
    """模块必须是完整的 stripped LuaJIT 2.0 字节码，根函数没有 upvalue。"""
    if len(b) > 4 * 1024 * 1024 or b[:5] != LJ_HEADER:
        raise CameraError("模块必须是 LuaJIT 2.0 stripped dump v1")
    p, root = 5, None
    while True:
        size, p = _uleb(b, p)
        if size == 0:
            break
        end = p + size
        if end > len(b):
            raise CameraError("模块原型越界")
        if size < 4:
            raise CameraError("模块原型头截断")
        root = p
        p = end
    if p != len(b) or root is None or b[root + 3] != 0:
        raise CameraError("模块必须完整且根闭包没有 upvalue")


def _patch_chunk(chunk, adapter, module_id):
    """原型和旧常量编号都不动；新常量按 KGC 序列化顺序（倒序）加在前面。"""
    if adapter[:5] != LJ_HEADER or adapter[-1:] != b"\0":
        raise CameraError("适配器字节码格式不符")
    if chunk[:5] != LJ_HEADER:
        raise CameraError("启动字节码不是已验证的 stripped LuaJIT v1")
    p, last = 5, None
    while True:
        prefix = p
        size, p = _uleb(chunk, p)
        if size == 0:
            break
        end = p + size
        if end > len(chunk):
            raise CameraError("原型长度无效")
        last = (prefix, p, end)
        p = end
    if p != len(chunk):
        raise CameraError("字节码尾部无效")
    if last is None:
        raise CameraError("缺少启动原型")
    prefix, start, end = last
    original = chunk[start:end]
    if len(original) < 4:
        raise CameraError("启动原型头截断")
    q = 4
    ngc, q = _uleb(original, q)
    nnum, q = _uleb(original, q)
    nbc, q = _uleb(original, q)
    code_start, code_end = q, q + nbc * 4
    uv_end = code_end + original[3] * 2
    if ngc > 65000 or nbc == 0 or uv_end > len(original) or original[code_end - 4:code_end] != bytes([71, 0, 1, 0]):
        raise CameraError("启动原型结构不匹配")
    body = bytearray(original[:4])
    body[0] |= 1           # PROTO_CHILD：根函数现在含有适配器闭包
    body[2] = max(body[2], 16)
    _put_uleb(body, ngc + 4)
    _put_uleb(body, nnum)
    _put_uleb(body, nbc + 5)
    body += original[code_start:code_end - 4]
    # pcall(预编译的适配器)；正式版虚拟机不许动态 loadstring
    body += _ins(52, 13, ngc)
    body += _ins(49, 14, ngc + 1)
    body += bytes([62, 13, 2, 3])  # pcall 成功标志、运行时错误
    body += _ins(53, 13, ngc + 2)
    body += _ins(53, 14, ngc + 3)
    body += bytes([71, 0, 1, 0])
    body += original[code_end:uv_end]
    if module_id == "captain":
        names = ["CaptainHelldiverBridgeBootError", "CaptainHelldiverBridgeBootOk"]
    else:
        names = ["HelldiversBridgeBootError_" + module_id, "HelldiversBridgeBootOk_" + module_id]
    for s in names:
        _put_uleb(body, len(s) + 5)
        body += s.encode()
    body.append(0)  # KGC_CHILD：先弹出新接上的适配器根函数
    _put_uleb(body, len("pcall") + 5)
    body += b"pcall"
    body += original[uv_end:]
    result = bytearray(chunk[:prefix])
    result += adapter[5:-1]
    _put_uleb(result, len(body))
    result += body
    result.append(0)
    return bytes(result)


def _boot_record(raw):
    """核对整个资源索引，找到启动脚本那条记录。只有启动脚本的数据可以变长。"""
    count = _u32(raw, 0)
    if count > 10000:
        raise CameraError("资源数量异常")
    pos = 260 + 16 * count
    found, ids = None, set()
    for i in range(count):
        rid = raw[pos:pos + 16]
        if len(rid) < 16:
            raise CameraError("资源记录截断")
        if rid in ids or rid != raw[260 + 16 * i:276 + 16 * i] or _u32(raw, pos + 16) != 1 or _u32(raw, pos + 20) != 0:
            raise CameraError("资源索引/分段格式不符")
        ids.add(rid)
        size = _u32(raw, pos + 28)
        if rid == BOOT_ID:
            if (found is not None or size < 8 or _u32(raw, pos + 24) != 0 or _u32(raw, pos + 32) != 0
                    or _u32(raw, pos + 36) + 8 != size or _u32(raw, pos + 40) != 2):
                raise CameraError("启动资源记录不符")
            found = (pos, size)
        pos += 36 + size
        if pos > len(raw):
            raise CameraError("资源越界")
    if pos != len(raw):
        raise CameraError("资源表未覆盖完整文件")
    if found is None:
        raise CameraError("未找到启动脚本资源")
    return found


def load_module():
    with open(CAMERA_LUAC, "rb") as f:
        b = f.read()
    if _sha(b) != CAMERA_LUAC_SHA:
        raise CameraError("分屏模块文件和记录的版本对不上（mod/camera/runtime.luac）")
    validate_bytecode(b)
    return b


def stack(raw, module=None, module_id="camera"):
    """raw = 解压后的核心包数据（build.py 压缩之前）。返回接好分屏的新数据。"""
    module = load_module() if module is None else module
    validate_bytecode(module)
    start, size = _boot_record(raw)
    boot = raw[start + 44:start + 36 + size]
    validate_bytecode(boot)
    if _sha(boot) != VANILLA_SCRIPT_SHA:
        raise CameraError("启动脚本版本未验证；其他资源可修改，但不能跳过启动脚本校验")
    chunk = _patch_chunk(boot, module, module_id)
    out = bytearray(raw[:start + 44])
    struct.pack_into("<I", out, start + 28, len(chunk) + 8)
    struct.pack_into("<I", out, start + 36, len(chunk))
    out += chunk
    out += raw[start + 36 + size:]
    return bytes(out)

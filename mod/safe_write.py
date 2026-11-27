"""写文件：先写旁边的临时文件再一步换上，写到一半被关 / 断电时原文件还是完整的。

2026-11-25（HD1-038，合并 PR #2 时定）：有的机器上安全软件不让新建临时文件或换名（WinError 5，
Oct0pu5 在 V1.08 遇到），这时才退回直接覆盖写。不再用 PowerShell 代写（杀毒容易误报，同权限也写不进）。
"""
import os


def write_bytes(path, data):
    path = os.fspath(path)
    tmp = path + ".hellbox-tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return
    except OSError:
        _remove(tmp)
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def write_text(path, text, crlf=False):
    """text 里用 \\n 换行；crlf=True 时写成 \\r\\n（和以前 Path.write_text 在 Windows 上写出来的一样）。"""
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    write_bytes(path, text.encode("utf-8"))


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

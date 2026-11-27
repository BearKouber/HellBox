"""
检查更新 / 一键更新（2026-11-26 用户要：「关于」里加检查更新，有新版能在软件里点一下就更新）。

- 检查：问 GitHub 最新的 Release（BearKouber/HellBox），版本号比现在的新就算有新版。
- 更新：下载 Release 里的 HellBox-Vx.yy.zip → 核对大小和说明里的 sha256 → 解压到临时文件夹（不碰程序目录）
  → 写一个 PowerShell 小脚本，HellBox 退出后把新文件盖到程序目录（只覆盖包里有的文件：
  设置、mod/backup 原版备份、mod/out 都不在包里，原样保留）→ 重新打开 HellBox。
- 结果写进 %APPDATA%/Arrowhead/Helldivers/hellbox/update-result.txt，下次打开时告诉玩家成没成。
- 只有打包好的 HellBox.exe 能自动更新；源码运行、全数据版不自动更新（全数据版的私有文件会被公开版盖掉）。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "BearKouber/HellBox"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
AGENT = "HellBox-updater"
TIMEOUT = 15
STATE_DIR = os.path.join(os.environ.get("APPDATA", ""), "Arrowhead", "Helldivers", "hellbox")
RESULT_FILE = os.path.join(STATE_DIR, "update-result.txt")
WORK = os.path.join(tempfile.gettempdir(), "HellBox-update")


class UpdateError(RuntimeError):
    pass


def parse_version(text):
    """"V1.10" / "v1.10" / "1.10.2" → (1, 10, 0) / (1, 10, 2)；认不出返回 None。"""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def _get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": accept})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def check(current):
    """返回 {"newer": bool, "version": "V1.12", "tag", "zip_url", "size", "sha256", "notes", "page"}。"""
    try:
        with _get(API) as r:
            data = json.loads(r.read().decode("utf-8"))
    except OSError as e:
        raise UpdateError(f"连不上 GitHub（{e}）。可以稍后再试，或点「发布页」手动下载。") from e
    except ValueError as e:
        raise UpdateError("GitHub 返回的内容看不懂，稍后再试。") from e
    tag = data.get("tag_name") or ""
    latest = parse_version(tag)
    if latest is None:
        raise UpdateError(f"认不出最新版本号：{tag}")
    asset = None
    for a in data.get("assets") or []:
        name = a.get("name") or ""
        if name.lower().startswith("hellbox-") and name.lower().endswith(".zip"):
            asset = a
            break
    notes = data.get("body") or ""
    sha = re.search(r"\b[0-9a-f]{64}\b", notes)
    cur = parse_version(current) or (0, 0, 0)
    return {
        "newer": latest > cur,
        "version": "V" + tag.strip().lstrip("vV"),
        "tag": tag,
        "zip_url": asset and asset.get("browser_download_url"),
        "size": asset and asset.get("size"),
        "sha256": sha.group(0) if sha else None,
        "notes": notes,
        "page": data.get("html_url") or PAGE,
    }


def download(info, progress=None):
    """下载新版 zip 到临时文件夹，核对大小和 sha256。返回 zip 路径。"""
    url = info.get("zip_url")
    if not url:
        raise UpdateError("最新版里没有安装包，请点「发布页」手动下载。")
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, os.path.basename(url.split("?")[0]) or "HellBox.zip")
    part = path + ".part"
    h = hashlib.sha256()
    got = 0
    try:
        with _get(url, accept="application/octet-stream") as r, open(part, "wb") as f:
            total = info.get("size") or int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if progress and total:
                    progress(got, total)
    except OSError as e:
        raise UpdateError(f"下载没完成（{e}）。可以再点一次，或点「发布页」手动下载。") from e
    if info.get("size") and got != info["size"]:
        raise UpdateError(f"下载的文件大小不对（{got} / {info['size']} 字节），再点一次试试。")
    if info.get("sha256") and h.hexdigest() != info["sha256"]:
        raise UpdateError("下载的文件和发布页写的校验码对不上，没有安装。再点一次试试。")
    os.replace(part, path)
    return path


def unpack(zip_path):
    """解压到临时文件夹，返回里面带 HellBox.exe 的那一层。"""
    dest = os.path.join(WORK, "new")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    root = os.path.realpath(dest)
    try:
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                target = os.path.realpath(os.path.join(dest, name))
                if target != root and not target.startswith(root + os.sep):
                    raise UpdateError(f"安装包里有奇怪的路径：{name}")
            z.extractall(dest)
    except zipfile.BadZipFile as e:
        raise UpdateError("安装包坏了，再点一次试试。") from e
    for d, _dirs, files in os.walk(dest):
        if "HellBox.exe" in files and os.path.isdir(os.path.join(d, "mod")):
            return d
    raise UpdateError("安装包里没找到 HellBox.exe。")


def can_self_update(app_dir):
    """能不能自动更新；不能时返回原因。"""
    if not getattr(sys, "frozen", False):
        return "现在是源码运行，不能自动更新。"
    if os.path.isfile(os.path.join(app_dir, "mod", "data_full")):
        return "全数据版不自动更新（会被公开版覆盖），请手动换新版。"
    probe = os.path.join(app_dir, ".hellbox-write-test")
    try:
        with open(probe, "w") as f:
            f.write("1")
        os.remove(probe)
    except OSError:
        return "HellBox 所在的文件夹写不进去，请手动换新版（或把 HellBox 放到别的文件夹）。"
    return None


def _ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


SCRIPT = r"""
$ErrorActionPreference = 'Continue'
$src = @SRC@
$dst = @DST@
$exe = Join-Path $dst 'HellBox.exe'
$result = @RESULT@
$version = @VERSION@
$log = @LOG@
try { Wait-Process -Id @PID@ -Timeout 60 -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 800
$ok = $false
for ($i = 0; $i -lt 5 -and -not $ok; $i++) {
    robocopy $src $dst /E /R:3 /W:1 /NP /NFL /NDL /LOG:$log | Out-Null
    $ok = $LASTEXITCODE -lt 8
    if (-not $ok) { Start-Sleep -Seconds 2 }
}
if ($ok) {
    [IO.File]::WriteAllText($result, "ok`n$version`n", (New-Object Text.UTF8Encoding $false))
} else {
    [IO.File]::WriteAllText($result, "fail`n$version`nrobocopy $LASTEXITCODE`n", (New-Object Text.UTF8Encoding $false))
}
Start-Process -FilePath $exe -WorkingDirectory $dst
"""


def launch_swap(new_dir, app_dir, version):
    """写好替换脚本并在后台启动；调用方随后退出 HellBox。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        os.remove(RESULT_FILE)
    except OSError:
        pass
    script = (SCRIPT.replace("@SRC@", _ps_quote(new_dir)).replace("@DST@", _ps_quote(app_dir))
              .replace("@RESULT@", _ps_quote(RESULT_FILE)).replace("@VERSION@", _ps_quote(version))
              .replace("@LOG@", _ps_quote(os.path.join(WORK, "robocopy.log"))).replace("@PID@", str(os.getpid())))
    ps1 = os.path.join(WORK, "apply-update.ps1")
    with open(ps1, "w", encoding="utf-8-sig", newline="\r\n") as f:  # 带 BOM，Windows PowerShell 5.1 才按 UTF-8 读中文路径
        f.write(script)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", ps1],
                     creationflags=flags, close_fds=True)


def take_result():
    """上次更新的结果（读完就删）：("ok" | "fail", 版本, 详情) 或 None。"""
    try:
        with open(RESULT_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
        os.remove(RESULT_FILE)
    except OSError:
        return None
    if not lines:
        return None
    return lines[0], (lines[1] if len(lines) > 1 else ""), (lines[2] if len(lines) > 2 else "")


def cleanup():
    """更新成功后清掉临时文件夹（下次打开时调用；删不掉就算了）。"""
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)

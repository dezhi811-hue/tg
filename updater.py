"""
GitHub Release 自动更新模块（仅支持 Windows PyInstaller .exe 形态）

流程：
1. GET https://api.github.com/repos/<REPO>/releases/latest
2. 对比 tag_name 与本地 __version__
3. 下载 TelegramFilter-Windows.zip
4. 解压到临时目录
5. 生成 updater.bat：等待当前 exe 退出 → 覆盖 → 重启 → 自删
6. 当前进程退出

注意：运行在源码模式（非 frozen）时拒绝执行，避免误操作工作目录。
"""
import os
import sys
import json
import zipfile
import tempfile
import subprocess
import urllib.request
from version import __version__

REPO = "dezhi811-hue/tg"
ASSET_NAME = "TelegramFilter-Windows.zip"
EXE_NAME = "TelegramFilter.exe"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parse_version(tag: str):
    """'v3.0.1' -> (3, 0, 1)；解析失败返回空元组。"""
    tag = tag.strip().lstrip("vV")
    parts = []
    for seg in tag.split("."):
        num = ""
        for ch in seg:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            return ()
        parts.append(int(num))
    return tuple(parts)


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def fetch_latest_release(timeout: int = 15) -> dict:
    """返回 GitHub API 的 release JSON；网络失败会抛异常。"""
    req = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "TelegramFilter-Updater"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_update():
    """
    返回 dict:
      {'has_update': bool, 'current': str, 'latest': str,
       'download_url': str|None, 'notes': str, 'raw_tag': str}
    """
    data = fetch_latest_release()
    raw_tag = data.get("tag_name", "")
    latest = _parse_version(raw_tag)
    current = _parse_version(__version__)

    download_url = None
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            download_url = asset.get("browser_download_url")
            break

    return {
        "has_update": bool(latest and current and latest > current),
        "current": __version__,
        "latest": raw_tag or "unknown",
        "download_url": download_url,
        "notes": data.get("body") or "",
        "raw_tag": raw_tag,
    }


def _download(url: str, dest: str, progress_cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": "TelegramFilter-Updater"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)


def apply_update(download_url: str, progress_cb=None):
    """
    下载并启动替换流程。成功时本函数返回后调用方应立即退出进程。
    非 frozen 模式会抛 RuntimeError。
    """
    if not is_frozen():
        raise RuntimeError("仅支持打包后的 .exe 进行自动更新；源码模式请使用 git pull")
    if os.name != "nt":
        raise RuntimeError("自动更新仅支持 Windows")
    if not download_url:
        raise RuntimeError("未找到下载地址")

    work_dir = tempfile.mkdtemp(prefix="tgfilter_upd_")
    zip_path = os.path.join(work_dir, ASSET_NAME)
    extract_dir = os.path.join(work_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    _download(download_url, zip_path, progress_cb)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    new_exe = None
    for root, _dirs, files in os.walk(extract_dir):
        for name in files:
            if name.lower() == EXE_NAME.lower():
                new_exe = os.path.join(root, name)
                break
        if new_exe:
            break
    if not new_exe:
        raise RuntimeError(f"更新包内未找到 {EXE_NAME}")

    current_exe = sys.executable
    bat_path = os.path.join(work_dir, "apply_update.bat")
    log_path = os.path.join(work_dir, "apply_update.log")

    # 等待当前 exe 退出（轮询 del 能否删除）→ 覆盖 → 启动新 exe → 自删
    bat = f"""@echo off
chcp 65001 >nul
setlocal
set "SRC={new_exe}"
set "DST={current_exe}"
set "LOG={log_path}"
echo [%date% %time%] 等待主程序退出... >> "%LOG%"
:wait
del "%DST%" >nul 2>&1
if exist "%DST%" (
    timeout /t 1 /nobreak >nul
    goto wait
)
echo [%date% %time%] 复制新版本 >> "%LOG%"
copy /y "%SRC%" "%DST%" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] 复制失败 >> "%LOG%"
    exit /b 1
)
echo [%date% %time%] 启动新版本 >> "%LOG%"
start "" "%DST%"
(goto) 2>nul & del "%~f0"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)

    # detached 启动 bat；当前进程随后应立即退出
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

"""Create the project-local environment. Run: python3 scripts/setup.py"""  # 建立此專案的虛擬環境，並安裝鎖定版本的相依套件
from pathlib import Path  # 以跨平台方式組合檔案路徑
import importlib.metadata  # 讀取目前環境已安裝的套件版本
import json  # 解析 pip 回傳的套件清單
import os  # 讀取資料目錄或測試網址等環境設定
import re  # 由鎖定內容取出並統一套件名稱
import subprocess  # 執行虛擬環境中的套件安裝命令
import sys  # 設定工具匯入路徑並檢查 Python 版本
import venv  # 建立此專案獨立的 Python 環境

ROOT = Path(__file__).resolve().parent.parent  # 設定專案或虛擬環境的絕對路徑
ENV = ROOT / '.venv'  # 設定專案或虛擬環境的絕對路徑
PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')  # 設定專案或虛擬環境的絕對路徑
LOCK = ROOT / 'requirements.lock'  # 環境內容的唯一來源
ENV_TOOLS = {'pip', 'setuptools', 'wheel'}  # 虛擬環境自帶的工具，不列入鎖定比對


def normalized(name):  # 統一套件名稱的大小寫與分隔符號
    return re.sub(r'[-_.]+', '-', name).lower()  # 回傳可直接比對的名稱


def lock_lines(lock_text):  # 取出鎖定內容中的需求行，略過空行與註解
    lines = (line.split('#')[0].strip() for line in lock_text.splitlines())  # 去除註解與換行差異
    return [line for line in lines if line]  # 只保留有內容的行


def locked_names(lock_text):  # 取出鎖定內容的全部套件名稱，不論環境條件
    return {normalized(re.split(r'[=<>!~;\s\[]', line, maxsplit=1)[0]) for line in lock_lines(lock_text)}  # 取版本符號之前的名稱


def lock_differences(lock_text, installed):  # 比對鎖定內容與已安裝套件，回傳差異說明
    from packaging.requirements import Requirement  # 只有鎖定環境內才有此套件，建立環境前不可載入
    versions = {normalized(name): version for name, version in installed.items()}  # 統一已安裝套件的名稱
    differences = []  # 收集所有差異
    for line in lock_lines(lock_text):  # 逐項核對鎖定需求
        requirement = Requirement(line)  # 解析版本與環境條件
        if requirement.marker is not None and not requirement.marker.evaluate():  # 依目前條件選擇下一步處理分支
            continue  # 此環境不需要這項鎖定
        version = versions.get(normalized(requirement.name))  # 取得實際安裝的版本
        if version is None or not requirement.specifier.contains(version, prereleases=True):  # 缺少或版本不符
            differences.append(f'{line}: installed {version}')  # 記錄需求與實際版本
    extras = set(versions) - locked_names(lock_text) - ENV_TOOLS  # 找出不在鎖定檔內的套件
    differences.extend(f'{name}: not in lock' for name in sorted(extras))  # 記錄多餘套件
    return differences  # 回傳完整差異


def installed_versions():  # 讀取目前 Python 環境已安裝的套件版本
    return {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}  # 回傳名稱與版本


def remove_unlocked_packages():  # 移除已不在鎖定檔內的套件，讓環境與鎖定一致
    listing = subprocess.run([str(PYTHON), '-m', 'pip', 'list', '--format=json', '--disable-pip-version-check'],
                             check=True, capture_output=True, text=True).stdout  # 讀取虛擬環境的套件清單
    installed = {normalized(item['name']) for item in json.loads(listing)}  # 統一已安裝套件的名稱
    extras = sorted(installed - locked_names(LOCK.read_text(encoding='utf-8')) - ENV_TOOLS)  # 找出需要移除的套件
    if extras:  # 依目前條件選擇下一步處理分支
        subprocess.run([str(PYTHON), '-m', 'pip', 'uninstall', '-y', *extras], check=True)  # 使用專案 Python 移除，失敗時回報非零結束碼


def base_python_exists():  # 由 pyvenv.cfg 確認建立此環境的 Python 是否還在
    config = ENV / 'pyvenv.cfg'  # 虛擬環境記錄基礎 Python 位置的檔案
    if not config.exists():  # 依目前條件選擇下一步處理分支
        return False  # 回傳環境結構不完整的結果
    for line in config.read_text(encoding='utf-8').splitlines():  # 逐行尋找基礎 Python 位置
        key, _, value = line.partition('=')  # 拆開設定名稱與內容
        if key.strip() == 'home':  # 依目前條件選擇下一步處理分支
            return any(Path(value.strip()).glob('python*'))  # 目錄內仍有直譯器才算存在
    return False  # 回傳設定檔沒有基礎 Python 位置的結果


def prepare_environment():  # 準備可供安裝套件的專案虛擬環境
    # 只依檔案結構判斷，不實際執行直譯器：暫時性的存取拒絕或啟動延遲不代表環境損壞，不可因此清除。
    if not (PYTHON.exists() and base_python_exists()):  # 依目前條件選擇下一步處理分支
        venv.EnvBuilder(with_pip=True, clear=True).create(ENV)  # 環境不存在或已確定損壞時才清除重建，並包含 pip


if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    if '--check' in sys.argv:  # 啟動器用此模式確認環境與鎖定一致，須以 .venv 的 Python 執行
        differences = lock_differences(LOCK.read_text(encoding='utf-8'), installed_versions())  # 比對實際安裝內容
        if differences:  # 依目前條件選擇下一步處理分支
            print('\n'.join(differences))  # 輸出差異供診斷
        raise SystemExit(1 if differences else 0)  # 以結束碼回報是否一致
    if sys.version_info < (3, 9):  # 依目前條件選擇下一步處理分支
        raise SystemExit('Life World requires Python 3.9 or later')  # 中止目前操作並向呼叫端傳遞錯誤
    prepare_environment()  # 確保後續安裝使用可執行的專案 Python
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', str(LOCK)], check=True)  # 使用專案 Python 安裝鎖定套件，安裝失敗時回報非零結束碼
    remove_unlocked_packages()  # 移除鎖定檔已不再列出的套件
    print('Ready. Run:', PYTHON, '-m app (from', ROOT, ')')  # 輸出此工具的執行結果

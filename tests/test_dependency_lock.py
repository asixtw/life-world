from pathlib import Path  # 以跨平台方式定位專案根目錄的鎖定檔

from packaging.requirements import Requirement  # 以 pip 相同的規格解析版本與環境條件
from packaging.utils import canonicalize_name  # 統一套件名稱的大小寫與分隔符號
import pytest  # 使用參數化案例

LOCK = Path(__file__).resolve().parent.parent / 'requirements.lock'  # scripts/setup.py 實際安裝的鎖定檔
NO_WINDOWS_WHEELS = {'greenlet': '3.2.5'}  # 已知完全沒有 Windows 預編譯檔的發行版本
WINDOWS = {'sys_platform': 'win32', 'platform_system': 'Windows', 'os_name': 'nt'}  # 評估環境條件時使用的 Windows 環境
SUPPORTED_PYTHONS = ['3.9', '3.10', '3.11', '3.12', '3.13', '3.14']  # 專案支援的 Python，壞版本只要在其一生效就算命中


def windows_requirements(text):  # 解析鎖定內容中，在任一支援的 Python 版本於 Windows 生效的需求
    environments = [{**WINDOWS, 'python_version': python, 'python_full_version': python + '.0'} for python in SUPPORTED_PYTHONS]  # 建立要評估的環境組合
    requirements = []  # 收集生效的需求
    for line in text.splitlines():  # 逐行處理鎖定內容
        content = line.split('#')[0].strip()  # 與 pip 相同，註解不屬於需求內容
        if not content:  # 略過空行與純註解
            continue  # 繼續處理下一行
        requirement = Requirement(content)  # 格式錯誤時直接失敗，避免無聲漏檢
        if requirement.marker is None or any(requirement.marker.evaluate(environment) for environment in environments):  # 任一環境生效就保留
            requirements.append(requirement)  # 保存生效的需求
    return requirements  # 回傳完整清單


def blocked_requirements(text):  # 找出會選到已知問題版本的需求
    blocked = []  # 收集命中的需求
    for requirement in windows_requirements(text):  # 逐項檢查生效的需求
        version = NO_WINDOWS_WHEELS.get(canonicalize_name(requirement.name))  # 取得此套件的問題版本
        if version and requirement.specifier.contains(version):  # 以版本語意比較，而不是比對字串
            blocked.append(requirement)  # 記錄命中的需求
    return blocked  # 回傳命中清單


@pytest.mark.parametrize('line', [  # 列出 pip 都接受、指向同一版本的寫法
    'greenlet==3.2.5',  # 標準寫法
    'greenlet==3.2.5  # Windows',  # 行末註解
    'greenlet == 3.2.5',  # 含空白
    'Greenlet==3.2.5',  # 大小寫不同
    'greenlet==3.2.5; sys_platform == "win32"',  # 限定 Windows 的環境條件
    'greenlet==3.2.5.0',  # 語意上等同 3.2.5 的版本寫法
    'greenlet==3.2.5; python_version < "3.10"',  # 只在舊版 Python 生效
    'greenlet==3.2.5; python_version >= "3.14"',  # 只在新版 Python 生效
])  # 結束參數清單
def test_blocked_pin_is_found_in_any_notation(line):  # 驗證：寫法差異不能繞過檢查
    assert blocked_requirements(line)  # 斷言會命中已知問題版本


@pytest.mark.parametrize('line', [  # 列出不會在支援的 Windows 環境選到問題版本的寫法
    'greenlet==3.2.5; sys_platform != "win32"',  # 只在非 Windows 生效
    'greenlet==3.2.5; python_version >= "3.15"',  # 只在尚未支援的 Python 生效
    'greenlet==3.2.4,!=3.2.5',  # 明確排除問題版本
])  # 結束參數清單
def test_safe_pin_is_allowed(line):  # 驗證：安全的寫法不會被誤判
    assert not blocked_requirements(line)  # 斷言不會誤判


def test_lock_avoids_releases_without_windows_wheels():  # 驗證：鎖定版本在沒有 C++ 編譯器的 Windows 也能安裝
    text = LOCK.read_text(encoding='utf-8')  # 取得鎖定內容
    assert any(requirement.name == 'greenlet' for requirement in windows_requirements(text))  # 確認解析有效，避免空清單讓測試假性通過
    assert not blocked_requirements(text)  # 命中時 pip 會改抓原始碼，setup.py 因缺編譯器而失敗

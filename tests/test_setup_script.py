import importlib.util  # 由檔案路徑載入不屬於套件的工具腳本
import json  # 組出模擬的 pip 套件清單
from pathlib import Path  # 以跨平台方式定位 scripts/setup.py
import subprocess  # 建立模擬的程序執行結果與逾時例外

import pytest  # 使用測試資源、參數化與替換機制

SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'setup.py'  # 受測的環境建立腳本


@pytest.fixture  # 註冊可由 pytest 注入並清理的測試資源
def setup_script(tmp_path, monkeypatch):  # 載入 setup.py，並將環境路徑與建立動作換成可檢查的替身
    spec = importlib.util.spec_from_file_location('lifeworld_setup', SCRIPT)  # 由檔案路徑描述工具腳本
    module = importlib.util.module_from_spec(spec)  # 建立獨立的模組物件
    spec.loader.exec_module(module)  # 執行頂層定義；主流程受 __main__ 保護不會啟動
    monkeypatch.setattr(module, 'ENV', tmp_path / '.venv')  # 不碰專案真實環境
    monkeypatch.setattr(module, 'PYTHON', tmp_path / '.venv' / 'python.exe')  # 指向測試用的直譯器路徑
    monkeypatch.setattr(module, 'LOCK', tmp_path / 'requirements.lock')  # 指向測試用的鎖定檔
    module.builds = []  # 記錄每次建立環境的目標與清除選項

    class Builder:  # 取代 venv.EnvBuilder，避免測試真的建立環境
        def __init__(self, **options):  # 保存呼叫端傳入的建立選項
            self.options = options  # 供 create 回報

        def create(self, path):  # 記錄建立要求
            module.builds.append((path, self.options.get('clear')))  # 保存目標路徑與是否清除舊內容

    monkeypatch.setattr(module.venv, 'EnvBuilder', Builder)  # 只在此測試期間替換
    return module  # 提供已隔離的腳本模組


@pytest.fixture  # 註冊可由 pytest 注入並清理的測試資源
def base_python(tmp_path):  # 建立模擬的基礎 Python 安裝目錄
    folder = tmp_path / 'Python314'  # 模擬建立環境時使用的 Python 位置
    folder.mkdir()  # 建立目錄
    (folder / 'python.exe').write_text('base', encoding='utf-8')  # 放入直譯器檔案
    return folder  # 提供給環境設定檔引用


def add_environment(module, home):  # 建立含 python.exe 與 pyvenv.cfg 的環境
    module.PYTHON.parent.mkdir(parents=True)  # 建立環境目錄
    module.PYTHON.write_text('not a program', encoding='utf-8')  # 模擬 venv 內的中介程序
    (module.ENV / 'pyvenv.cfg').write_text(f'home = {home}\nversion = 3.14.7\n', encoding='utf-8')  # 記錄基礎 Python 位置


def test_missing_environment_is_created_from_empty_state(setup_script):  # 驗證：沒有直譯器時清除殘留內容再建立
    setup_script.prepare_environment()  # 執行環境準備
    assert setup_script.builds == [(setup_script.ENV, True)]  # 斷言只建立一次且會清除半成品


def test_environment_is_rebuilt_when_base_python_is_gone(setup_script, tmp_path):  # 驗證：基礎 Python 被移除後重建
    add_environment(setup_script, tmp_path / 'removed-python')  # 設定檔指向已不存在的位置
    setup_script.prepare_environment()  # 執行環境準備
    assert setup_script.builds == [(setup_script.ENV, True)]  # 斷言改為重建，不沿用損壞環境


def test_environment_without_config_is_rebuilt(setup_script):  # 驗證：缺少 pyvenv.cfg 的環境視為損壞
    setup_script.PYTHON.parent.mkdir(parents=True)  # 建立環境目錄
    setup_script.PYTHON.write_text('not a program', encoding='utf-8')  # 只有直譯器檔案，沒有設定檔
    setup_script.prepare_environment()  # 執行環境準備
    assert setup_script.builds == [(setup_script.ENV, True)]  # 斷言改為重建


def test_intact_environment_is_kept(setup_script, base_python):  # 驗證：結構完整的環境不重建，保留已安裝套件
    add_environment(setup_script, base_python)  # 建立基礎 Python 仍存在的環境
    setup_script.prepare_environment()  # 執行環境準備
    assert setup_script.builds == []  # 斷言沒有清除既有環境


@pytest.mark.parametrize('failure', [PermissionError('denied'), subprocess.TimeoutExpired('python', 1)])  # 暫時性存取拒絕與啟動延遲
def test_temporary_failure_never_clears_intact_environment(setup_script, base_python, monkeypatch, failure):  # 驗證：防毒鎖定或延遲不會誤刪可用環境
    add_environment(setup_script, base_python)  # 建立基礎 Python 仍存在的環境

    def fail(*args, **kwargs):  # 模擬執行直譯器時發生暫時性問題
        raise failure  # 拋出參數指定的例外

    monkeypatch.setattr(setup_script.subprocess, 'run', fail)  # 只在此測試期間替換
    setup_script.prepare_environment()  # 執行環境準備
    assert setup_script.builds == []  # 斷言環境未被清除，判斷也不依賴執行直譯器


LOCK_TEXT = 'fastapi==0.128.8\r\n# comment\r\ntyping-extensions==4.16.0  # note\r\ncolorama==0.4.6; sys_platform == "no-such-platform"\r\n'  # 含 CRLF、註解、行末註解與不生效的環境條件


def test_matching_environment_has_no_differences(setup_script):  # 驗證：名稱寫法不同但內容一致時視為相符
    assert setup_script.lock_differences(LOCK_TEXT, {'FastAPI': '0.128.8', 'typing_extensions': '4.16.0', 'pip': '26.2.1', 'setuptools': '80.0.0'}) == []  # 斷言 pip 工具與名稱差異不算差異


@pytest.mark.parametrize('installed, package', [  # 列出環境與鎖定不一致的情況
    ({'fastapi': '0.127.0', 'typing-extensions': '4.16.0'}, 'fastapi'),  # 版本不同
    ({'typing-extensions': '4.16.0'}, 'fastapi'),  # 缺少套件
    ({'fastapi': '0.128.8', 'typing-extensions': '4.16.0', 'tomli': '2.5.0'}, 'tomli'),  # 多出未鎖定套件
])  # 結束參數清單
def test_differences_are_reported(setup_script, installed, package):  # 驗證：版本不同、缺少與多餘都會回報
    differences = setup_script.lock_differences(LOCK_TEXT, installed)  # 比對環境與鎖定內容
    assert any(package in difference for difference in differences)  # 斷言差異訊息指出該套件


def test_package_with_inactive_marker_is_neither_required_nor_extra(setup_script):  # 驗證：環境條件不生效的套件不強制安裝，裝了也不算多餘
    installed = {'fastapi': '0.128.8', 'typing-extensions': '4.16.0', 'colorama': '0.4.6'}  # 環境含不生效的 colorama
    assert setup_script.lock_differences(LOCK_TEXT, installed) == []  # 斷言不回報差異


def record_pip(setup_script, monkeypatch, packages):  # 以替身回應 pip list，並記錄之後的 pip 呼叫
    calls = []  # 保存所有 pip 命令

    def run(command, **kwargs):  # 模擬 subprocess.run
        calls.append(command)  # 記錄命令內容
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([{'name': name, 'version': '1'} for name in packages]))  # 回傳模擬的 pip list 輸出

    monkeypatch.setattr(setup_script.subprocess, 'run', run)  # 只在此測試期間替換
    return calls  # 提供給測試檢查


def test_unlocked_packages_are_removed(setup_script, monkeypatch):  # 驗證：鎖定檔移除的套件會從環境移除
    setup_script.LOCK.write_text('fastapi==0.128.8\n', encoding='utf-8')  # 鎖定檔已不含 tomli
    calls = record_pip(setup_script, monkeypatch, ['fastapi', 'tomli', 'pip'])  # 環境仍殘留 tomli
    setup_script.remove_unlocked_packages()  # 執行同步
    assert calls[-1][-3:] == ['uninstall', '-y', 'tomli']  # 斷言只移除多餘套件，不動 pip


def test_nothing_is_removed_when_environment_matches(setup_script, monkeypatch):  # 驗證：環境一致時不執行移除
    setup_script.LOCK.write_text('fastapi==0.128.8\n', encoding='utf-8')  # 鎖定檔內容
    calls = record_pip(setup_script, monkeypatch, ['fastapi', 'pip'])  # 環境與鎖定一致
    setup_script.remove_unlocked_packages()  # 執行同步
    assert len(calls) <= 1 and not any('uninstall' in call for call in calls)  # 斷言沒有移除動作

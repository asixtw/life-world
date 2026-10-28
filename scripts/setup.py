"""Create the project-local environment. Run: python3 scripts/setup.py"""  # 建立此專案的虛擬環境，並安裝鎖定版本的相依套件
from pathlib import Path  # 以跨平台方式組合檔案路徑
import os  # 讀取資料目錄或測試網址等環境設定
import subprocess  # 執行虛擬環境中的套件安裝命令
import sys  # 設定工具匯入路徑並檢查 Python 版本
import venv  # 建立此專案獨立的 Python 環境

ROOT = Path(__file__).resolve().parent.parent  # 設定專案或虛擬環境的絕對路徑
ENV = ROOT / '.venv'  # 設定專案或虛擬環境的絕對路徑
PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')  # 設定專案或虛擬環境的絕對路徑

if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    if sys.version_info < (3, 9):  # 依目前條件選擇下一步處理分支
        raise SystemExit('Life World requires Python 3.9 or later')  # 中止目前操作並向呼叫端傳遞錯誤
    if not PYTHON.exists():  # 依目前條件選擇下一步處理分支
        venv.EnvBuilder(with_pip=True).create(ENV)  # 虛擬環境尚不存在時才建立，並包含 pip
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.lock')], check=True)  # 使用專案 Python 安裝鎖定套件，安裝失敗時回報非零結束碼
    print('Ready. Run:', PYTHON, '-m app (from', ROOT, ')')  # 輸出此工具的執行結果

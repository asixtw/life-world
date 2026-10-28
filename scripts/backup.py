"""Consistent SQLite backup, including committed WAL content."""  # 使用 SQLite 備份 API 取得包含已提交 WAL 資料的一致性備份
from pathlib import Path  # 以跨平台方式組合檔案路徑
import argparse  # 解析工具的命令列參數
import sqlite3  # 讀寫 SQLite、執行遷移與一致性備份

ROOT = Path(__file__).resolve().parent.parent  # 設定專案或虛擬環境的絕對路徑

if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    parser = argparse.ArgumentParser(description='Create a consistent Life World SQLite backup')  # 準備備份命令列參數解析器
    parser.add_argument('destination', type=Path)  # 宣告可接受的命令列參數與預設值
    parser.add_argument('--source', type=Path, default=ROOT / 'data' / 'lifeworld.sqlite3')  # 宣告可接受的命令列參數與預設值
    args = parser.parse_args()  # 準備使用者提供的來源與備份目的路徑
    if not args.source.is_file():  # 依引用來源是否存在選擇處理方式
        parser.error('Source database does not exist')  # 來源不存在時停止，不建立空白備份
    if args.destination.exists():  # 依目前條件選擇下一步處理分支
        parser.error('Destination already exists; refusing to overwrite')  # 拒絕覆寫既有備份
    args.destination.parent.mkdir(parents=True, exist_ok=True)  # 先建立備份目的資料夾
    with sqlite3.connect(args.source.resolve().as_uri() + '?mode=ro', uri=True) as source:  # 以唯讀方式開啟來源，避免誤建或修改正式資料庫
        with sqlite3.connect(args.destination) as destination:  # 以區塊生命週期確保資源在結束時關閉
            source.backup(destination)  # 以 SQLite 一致性備份納入已提交的 WAL 內容
    args.destination.chmod(0o600)  # 將檔案權限限制為目前使用者可讀寫
    print('Backup created:', args.destination)  # 輸出此工具的執行結果

from pathlib import Path  # 以跨平台方式組合檔案路徑
from tempfile import TemporaryDirectory  # 建立測試或匯出使用的暫存目錄
import json  # 序列化資料與還原資料庫中的清單
import sys  # 設定工具匯入路徑並檢查 Python 版本

ROOT = Path(__file__).resolve().parent.parent  # 設定專案或虛擬環境的絕對路徑
sys.path.insert(0, str(ROOT))  # 讓此腳本在任意工作目錄都能匯入專案 App
from app.main import create_app  # 使用正式 App 工廠建立服務或測試實例

if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    with TemporaryDirectory() as directory:  # 以區塊生命週期確保資源在結束時關閉
        schema = create_app(data_dir=directory).openapi()  # 準備由實際 App 匯出的 OpenAPI 規格
    (ROOT / 'docs' / 'openapi.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n')  # 將工具產生的內容寫入指定文字檔
    print('Exported docs/openapi.json')  # 輸出此工具的執行結果

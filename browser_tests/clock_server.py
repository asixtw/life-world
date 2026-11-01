"""僅供隔離 Chromium 跨日驗收的啟動器，不提供調時 HTTP API。"""  # 不用於正式部署。
import argparse  # 明確指定隔離資料與時鐘檔。
from datetime import datetime, timezone  # 平時使用真實 UTC。
from pathlib import Path  # 驗證資料目錄與控制檔。
import uvicorn  # 使用現有伺服器依賴。
from app.main import create_app  # 載入正式 App 工廠。


def main():  # 只有直接啟動時建立測試服務。
    parser = argparse.ArgumentParser(description='Isolated Life World browser acceptance server')  # 提供可重現的驗收命令。
    parser.add_argument('--data-dir', required=True, type=Path)  # 禁止省略資料位置而誤用預設 DB。
    parser.add_argument('--clock-file', required=True, type=Path)  # 專用控制檔，不提供公網調時能力。
    parser.add_argument('--port', type=int, default=8002)  # 與日常服務分開。
    args = parser.parse_args()  # 讀取明確的測試設定。
    real_data = Path(__file__).resolve().parents[1] / 'data'  # 正式本機資料根目錄。
    directory = args.data_dir.resolve()  # 避免相對路徑與符號連結繞過。
    if directory == real_data or real_data in directory.parents: parser.error('不能使用正式資料目錄，請選 /tmp 下的隔離目錄')  # 在任何建檔前拒絕。
    clock_file = args.clock_file.resolve()  # 專用控制檔位置。
    if real_data == clock_file or real_data in clock_file.parents: parser.error('時鐘控制檔不能寫入正式資料目錄')  # 不污染正式備份或資料。
    clock_file.parent.mkdir(parents=True, exist_ok=True)  # 只建立指定的測試目錄。
    if not clock_file.exists(): clock_file.write_text('realtime')  # 不覆寫原有控制檔。
    def clock():  # 由測試程序切換短暫的固定時刻。
        value = clock_file.read_text().strip()  # 不將內容當成程式執行。
        instant = datetime.now(timezone.utc) if value == 'realtime' else datetime.fromisoformat(value)  # 一般旅程不凍結時鐘。
        if instant.tzinfo is None: raise ValueError('測試時鐘必須帶時區')  # 不依主機當地時區猜測。
        return instant  # 交給既有服務判定生命週期。
    clock()  # 啟動前驗證控制檔格式。
    uvicorn.run(create_app(data_dir=directory, clock=clock), host='127.0.0.1', port=args.port, access_log=False)  # 僅監聽本機。


if __name__ == '__main__': main()  # 匯入此工具不會啟動服務或接觸 DB。

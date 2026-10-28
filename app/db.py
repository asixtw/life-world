"""One connection per operation and serialized, atomic writes."""  # 每次操作獨立連線，寫入在同一交易內提交或全部回滾
from contextlib import contextmanager  # 以 with 管理交易生命週期
from pathlib import Path  # 以跨平台方式組合檔案路徑
import sqlite3  # 讀寫 SQLite、執行遷移與一致性備份


class Database:  # 管理 SQLite 遷移與每次操作的交易連線
    def __init__(self, data_dir):  # 建立資料目錄並依序套用未執行的遷移
        self.directory = Path(data_dir).resolve()  # 將資料目錄轉成絕對路徑，避免隨啟動位置改變
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)  # 建立資料目錄，新目錄僅允許目前使用者存取
        self.path = self.directory / 'lifeworld.sqlite3'  # 固定此 App 的 SQLite 資料庫檔名
        connection = sqlite3.connect(str(self.path), isolation_level=None, timeout=20)  # 準備獨立 SQLite 資料庫連線
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            connection.execute('PRAGMA journal_mode=WAL')  # 啟用 WAL，讓已提交資料可供並行讀取
            connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)')  # 定義已套用遷移版本
            for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):  # 逐項處理清單中的資料，保留目前交易或查詢條件
                if not connection.execute('SELECT 1 FROM schema_migrations WHERE version=?', (path.name,)).fetchone():  # 查詢已套用遷移版本；值以參數傳入
                    connection.executescript('BEGIN IMMEDIATE;\n' + path.read_text() +
                                             "\nINSERT INTO schema_migrations VALUES ('" + path.name + "');\nCOMMIT;")  # 在同一寫入交易套用專案內的 SQL 遷移並記錄版本；檔名由專案提供
        finally:  # 不論成功或失敗都執行必要清理
            connection.close()  # 關閉已使用完畢的資源
        self.path.chmod(0o600)  # 將檔案權限限制為目前使用者可讀寫

    @contextmanager  # 允許呼叫端以 with 管理交易生命週期
    def connect(self, write=False):  # 開啟獨立交易；成功提交、失敗回滾並確實關閉連線
        connection = sqlite3.connect(str(self.path), isolation_level=None, timeout=20)  # 準備獨立 SQLite 資料庫連線
        connection.row_factory = sqlite3.Row  # 讓查詢資料列可依欄位名稱讀取
        connection.execute('PRAGMA foreign_keys=ON')  # 啟用 SQLite 外鍵完整性檢查
        connection.execute('PRAGMA busy_timeout=20000')  # 遇到寫入鎖時等待最多二十秒
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')  # 寫入時先取得寫鎖；純讀取使用一般交易
            yield connection  # 提供區塊或測試使用的資源，之後繼續清理
            connection.commit()  # 提交本次交易的全部修改
        except BaseException:  # 處理此類預期例外並保留明確失敗結果
            connection.rollback()  # 撤回失敗交易的全部修改
            raise  # 中止目前操作並向呼叫端傳遞錯誤
        finally:  # 不論成功或失敗都執行必要清理
            connection.close()  # 關閉已使用完畢的資源

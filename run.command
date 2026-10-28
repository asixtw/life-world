#!/bin/zsh
# 使用 macOS 的 zsh；上方 shebang 必須保留在第一行。
cd -- "${0:A:h}" # 切換到啟動器所在的專案目錄，避免雙擊時使用錯誤工作路徑
if [[ ! -x .venv/bin/python ]]; then # 確認專案虛擬環境內的 Python 已存在且可執行
  print "請先執行：python3 scripts/setup.py" # 缺少環境時告知建立方式
  exit 1 # 以失敗結束碼停止，避免使用其他環境誤啟動
fi # 結束環境檢查
exec .venv/bin/python -m app # 以專案 Python 啟動本機 App，並交接目前程序

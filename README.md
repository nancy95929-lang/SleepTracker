# 睡眠日記 SleepTracker v0.8

## 這版修正

- PDF 報告固定為單頁 A4
- PDF 改成完整美編版：
  - 奶油色背景
  - 月亮 / 雲朵 / 星星裝飾
  - 四個摘要資訊卡
  - 最近 7 筆睡眠趨勢圖
  - 14 天連續打卡視覺化
  - 最近 5 筆睡眠紀錄
- PDF 為繁體中文
- 原本 App 的繁中、高對比、月曆、分析、一天一筆等功能保留
- 新增 `pyproject.toml`，開始整理成 Flet iOS build 專案結構

## Windows 執行

```powershell
python -m pip install -r requirements.txt
python main.py
```

## iOS 下一階段

Flet 的 iOS `.ipa` / Simulator build 必須在 macOS 上執行。
此專案已開始整理 iOS build metadata，但正式打包前仍需：

1. Mac + Xcode
2. Flet / Flutter iOS build 環境
3. Apple Developer 簽名 / provisioning profile（實機或 App Store）
4. 若要 Screen Time / Device Activity，加入 Family Controls capability 與原生 Swift extension
5. 檢查 Python binary packages 的 iOS wheels。尤其 matplotlib 目前是桌面 PDF/PNG 匯出用途，iOS 版可能要改為原生輸出或拆成平台限定功能。


## v0.9 修正

- 修正分析頁「最近 7 天 / 最近 30 天 / 全部紀錄」無法切換。
- 不再使用 Flet 1.0.3 版本相容性較差的 Dropdown 切換事件。
- 改為三顆明確的區間按鈕；目前選取的區間會以深綠色顯示。
- 每次切換都會立即重新計算平均睡眠、紀錄天數、平均入睡/起床、最長/最短睡眠與圖表。


## v1.0 修正

- PNG 匯出改成與 PDF 完全相同的 A4 美編版型。
- 現在按「PNG 圖表」匯出的不再是單純柱狀圖，而是和 PDF 一樣的完整視覺報告。
- 更方便之後在 iPhone 相簿直接存圖、分享或列印。


## v1.1 iPhone 13 響應式介面修正

- 移除首頁睡眠按鈕固定 340px 寬度，改成依螢幕自動撐滿。
- App 左右安全邊距縮小，避免 iPhone 窄螢幕被裁切。
- 月曆 7 欄改為等比例伸縮，不再使用固定 40px 欄寬。
- 「7 天 / 30 天 / 全部」分析按鈕改為等寬短標籤。
- 時間選擇按鈕由「滾輪選擇」縮短成「選擇」。
- 匯出、編輯、刪除等按鈕列支援自動換行。
- 圖表欄位改為平均分配可用寬度。
- 連續打卡圓點縮小，降低 iPhone 小螢幕橫向壓力。


## v1.2 iPhone 分享 / 相簿流程

新增：
- 設定 → iPhone 分享 → 分享 PNG
- 設定 → iPhone 分享 → 分享 PDF
- 使用 Flet `Share` service 呼叫 iOS 原生分享面板
- PNG 以 `ShareFile.from_bytes()` 傳給 iPhone，不會把 Windows 路徑直接丟給手機
- iPhone 分享 PNG 後選「儲存影像」，即可放進照片 App
- PDF 可存到「檔案」、AirDrop、郵件、LINE 等支援項目

注意：
- 在 `flet run --ios main.py` 開發模式下，Python 還是在 Windows 執行，所以報告會先由 Windows 產生，再用 bytes 傳給 iPhone。
- 「直接不經分享面板自動寫入照片 App」需要正式 iOS Photos 權限 / 原生能力，不是這版的測試目標。


## v1.3 睡後手機偵測流程骨架

新增：
- 首頁「睡後手機活動」狀態卡。
- 按「我要睡了」後建立監測工作階段狀態。
- 起床後結束監測工作階段。
- SQLite 新增 `activity_status`、`monitoring_started_at`、`monitoring_ended_at`。
- 保留 `post_checkin_screen_minutes`、`last_phone_activity_time`、`last_phone_app` 作為正式 iOS 回寫欄位。
- `ios_native/` 新增 Swift / DeviceActivity Monitor Extension 架構骨架。

Windows + Flet iPhone 預覽模式不會偽造 Screen Time 資料，因此狀態卡會顯示「等待 iOS」。

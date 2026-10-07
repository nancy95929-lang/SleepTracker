# iOS Screen Time / Device Activity 骨架（v1.3）

目前 Windows + Flet iPhone 預覽版只完成：

1. 按「我要睡了」時，在 SQLite 標記 `waiting_for_ios`。
2. 首頁出現「睡後手機活動」狀態卡。
3. 起床時結束這次監測工作階段。
4. 若未來原生 iOS 層寫回資料，首頁可顯示：
   - 睡後使用分鐘
   - 最後活動時間
   - App 名稱（只有 Apple 權限允許時）

## 正式 iOS target 需要

- Xcode 15+
- Family Controls capability
- Device Activity Monitor Extension target
- App Group（建議用於主 App 與 extension 交換摘要資料）
- Apple Developer entitlement / provisioning

`SleepScreenTimeManager.swift` 與 `SleepDeviceActivityMonitor.swift` 是架構骨架，不會在 Windows Flet 預覽版執行。

## 隱私限制

一般 Screen Time API 以隱私保護為核心。若 App 沒有取得 Apple 的「App and Website Usage」資料存取 entitlement，就不能假設可以拿到所有實際 App 名稱 / bundle ID。App 應在拿不到名稱時退化為「睡後使用時間 + 最後活動時間」。

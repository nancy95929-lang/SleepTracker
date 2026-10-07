import DeviceActivity
import Foundation

/// Device Activity Monitor Extension 骨架。
/// 正式 Xcode 專案中要建立獨立 Device Activity Monitor Extension target。
@available(iOS 16.0, *)
final class SleepDeviceActivityMonitor: DeviceActivityMonitor {
    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        // 正式版：記錄監測開始，或寫入 App Group shared storage。
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        // 正式版：結算睡後裝置活動摘要。
    }

    override func eventDidReachThreshold(
        _ event: DeviceActivityEvent.Name,
        activity: DeviceActivityName
    ) {
        super.eventDidReachThreshold(event, activity: activity)
        // 正式版：可在到達設定的使用門檻時寫入 shared storage。
    }
}

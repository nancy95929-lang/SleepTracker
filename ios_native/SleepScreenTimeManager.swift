import Foundation
import FamilyControls
import DeviceActivity

/// v1.3 骨架：正式 iOS target 中使用。
/// 需要在 Xcode 加入 Family Controls capability，並依實際 entitlement 狀態調整。
@available(iOS 16.0, *)
final class SleepScreenTimeManager: ObservableObject {
    static let shared = SleepScreenTimeManager()

    private let center = DeviceActivityCenter()
    private let authorizationCenter = AuthorizationCenter.shared
    private let activityName = DeviceActivityName("sleep.session")

    @Published private(set) var isAuthorized = false
    @Published private(set) var isMonitoring = false

    private init() {}

    @MainActor
    func requestAuthorization() async throws {
        try await authorizationCenter.requestAuthorization(for: .individual)
        isAuthorized = authorizationCenter.authorizationStatus == .approved
    }

    func startBedtimeMonitoring(startHour: Int, startMinute: Int) throws {
        let schedule = DeviceActivitySchedule(
            intervalStart: DateComponents(hour: startHour, minute: startMinute),
            intervalEnd: DateComponents(hour: 12, minute: 0),
            repeats: false
        )

        try center.startMonitoring(
            activityName,
            during: schedule
        )

        isMonitoring = true
    }

    func stopBedtimeMonitoring() {
        center.stopMonitoring([activityName])
        isMonitoring = false
    }
}

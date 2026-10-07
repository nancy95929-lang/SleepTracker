import calendar
import csv
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

import database
from report_export import export_a4_sleep_report, export_a4_sleep_visual


# =============================
# 高對比日系奶油色
# =============================
BG = "#F6F0E8"
CARD = "#FFFEFC"
TEXT = "#272A27"
SUBTEXT = "#454A45"
MUTED = "#555B55"
ACCENT = "#8DA38A"
ACCENT_DARK = "#566D58"
ACCENT_LIGHT = "#E2EADF"
BLUE = "#8EA9BC"
PINK = "#D7A8A4"
YELLOW = "#DDBE72"
ERROR = "#A14949"
LINE = "#D9D2C7"

FONT = "Microsoft JhengHei UI"
DISPLAY_FONT = "Microsoft JhengHei UI"


def main(page: ft.Page):
    database.create_table()

    page.title = "睡眠日記"
    page.window.width = 390
    page.window.height = 844
    # 手機版縮小左右安全邊距，避免 iPhone 窄螢幕裁切
    page.padding = ft.Padding.only(left=12, right=12, top=12, bottom=8)
    page.bgcolor = BG

    # iOS / Android / 桌面平台分享服務
    # Flet 1.0+ 的 Service 建立後即可直接使用，不需加到 page.overlay。
    share_service = ft.Share()

    records_cache = []
    journal_month = datetime.now().replace(day=1)

    def reload_records():
        nonlocal records_cache
        records_cache = database.get_all_records()

    reload_records()

    content_area = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # =============================
    # 共用工具
    # =============================
    def t(value="", **kwargs):
        kwargs.setdefault("font_family", FONT)
        kwargs.setdefault("color", TEXT)
        return ft.Text(value, **kwargs)

    def parse_sleep_times(date_text, sleep_text, wake_text):
        sleep_time = datetime.strptime(
            f"{date_text} {sleep_text}",
            "%Y-%m-%d %H:%M",
        )

        wake_time = datetime.strptime(
            f"{date_text} {wake_text}",
            "%Y-%m-%d %H:%M",
        )

        if wake_time <= sleep_time:
            wake_time += timedelta(days=1)

        return sleep_time, wake_time

    def duration_minutes(record):
        return record["hours"] * 60 + record["minutes"]

    def minutes_to_text(minutes):
        return f"{minutes // 60} 小時 {minutes % 60:02d} 分"

    def average_sleep_clock(records):
        if not records:
            return "--:--"

        values = []

        for record in records:
            sleep = record["sleep_time"]
            minutes = sleep.hour * 60 + sleep.minute

            if sleep.hour < 12:
                minutes += 24 * 60

            values.append(minutes)

        avg = int(sum(values) / len(values)) % (24 * 60)
        return f"{avg // 60:02d}:{avg % 60:02d}"

    def average_wake_clock(records):
        if not records:
            return "--:--"

        values = [
            r["wake_time"].hour * 60 + r["wake_time"].minute
            for r in records
        ]

        avg = int(sum(values) / len(values))
        return f"{avg // 60:02d}:{avg % 60:02d}"

    def card(content, padding=18, bgcolor=CARD):
        return ft.Container(
            content=content,
            bgcolor=bgcolor,
            padding=padding,
            border_radius=24,
        )

    def completed_records():
        return [
            r for r in records_cache
            if r["wake_time"] is not None
        ]

    def styled_field(label, value="", hint_text=None, read_only=False, expand=False):
        return ft.TextField(
            label=label,
            value=value,
            hint_text=hint_text,
            read_only=read_only,
            expand=expand,
            color=TEXT,
            border_color=ACCENT_DARK,
            focused_border_color=ACCENT_DARK,
            label_style=ft.TextStyle(
                color=TEXT,
                size=13,
                font_family=FONT,
            ),
            hint_style=ft.TextStyle(
                color=SUBTEXT,
                size=12,
                font_family=FONT,
            ),
            text_style=ft.TextStyle(
                color=TEXT,
                size=15,
                font_family=FONT,
            ),
        )

    def time_to_seconds(value):
        hour, minute = map(int, value.split(":"))
        return hour * 3600 + minute * 60

    # =============================
    # 時間滾輪
    # =============================
    def open_time_wheel(target_field, initial_time):
        try:
            seconds = time_to_seconds(initial_time)
        except Exception:
            seconds = 23 * 3600 + 30 * 60

        preview = t(
            initial_time,
            size=24,
            weight=ft.FontWeight.BOLD,
        )

        picker = ft.CupertinoTimerPicker(
            value=seconds,
            minute_interval=1,
            mode=ft.CupertinoTimerPickerMode.HOUR_MINUTE,
        )

        def changed(e):
            total = int(e.data)
            hour = (total // 3600) % 24
            minute = (total % 3600) // 60
            preview.value = f"{hour:02d}:{minute:02d}"
            preview.update()

        picker.on_change = changed

        def confirm(e):
            target_field.value = preview.value
            target_field.update()
            page.pop_dialog()

        sheet = ft.CupertinoBottomSheet(
            height=310,
            padding=ft.Padding.only(
                top=12,
                left=16,
                right=16,
                bottom=12,
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            t(
                                "選擇時間",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            preview,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    picker,
                    ft.Button(
                        content="完成",
                        on_click=confirm,
                    ),
                ],
                spacing=8,
            ),
        )

        page.show_dialog(sheet)

    def time_field(label, value):
        field = styled_field(
            label=label,
            value=value,
            read_only=True,
            expand=True,
        )

        button = ft.Button(
            content="選擇",
            on_click=lambda e: open_time_wheel(
                field,
                field.value or value,
            ),
        )

        return field, ft.Row(
            [field, button],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # =============================
    # 首頁裝飾
    # =============================
    def header_card():
        return card(
            ft.Row(
                [
                    ft.Container(
                        content=t("☾", size=38),
                        width=62,
                        height=62,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ACCENT_LIGHT,
                        border_radius=31,
                    ),
                    ft.Column(
                        [
                            t(
                                "睡眠日記",
                                size=27,
                                weight=ft.FontWeight.BOLD,
                                font_family=DISPLAY_FONT,
                            ),
                            t(
                                "今天也辛苦了，準備好好休息吧。",
                                size=13,
                                color=SUBTEXT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    t("🐑", size=31),
                ]
            ),
            bgcolor="#FFF9F0",
        )

    def bedtime_tip():
        return ft.Container(
            content=ft.Row(
                [
                    t("💤", size=22),
                    t(
                        "按下「我要睡了」後，就把手機也一起休息。",
                        size=12,
                        color=SUBTEXT,
                        expand=True,
                    ),
                    t("☁", size=20),
                ]
            ),
            bgcolor="#EEE8DE",
            border_radius=18,
            padding=12,
        )

    # =============================
    # 連續打卡
    # =============================
    def build_streak_visual():
        completed_dates = {
            r["sleep_time"].date()
            for r in completed_records()
        }

        today = datetime.now().date()
        days = [
            today - timedelta(days=i)
            for i in range(13, -1, -1)
        ]

        rows = []

        for start in (0, 7):
            controls = []

            for day in days[start:start + 7]:
                hit = day in completed_dates

                controls.append(
                    ft.Column(
                        [
                            ft.Container(
                                content=t(
                                    "✓" if hit else "·",
                                    size=17,
                                    color="#FFFFFF" if hit else MUTED,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                width=30,
                                height=30,
                                border_radius=15,
                                bgcolor=ACCENT_DARK if hit else "#E4DED4",
                                alignment=ft.Alignment.CENTER,
                            ),
                            t(
                                day.strftime("%m/%d"),
                                size=8,
                                color=SUBTEXT,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=3,
                    )
                )

            rows.append(
                ft.Row(
                    controls,
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                )
            )

        return ft.Column(rows, spacing=8)

    def build_phone_activity_card(active_record=None, last_record=None):
        """首頁睡後手機活動狀態卡。開發預覽版只顯示流程，不偽造 iOS 系統資料。"""
        record = active_record or last_record

        if not record:
            status_title = "尚未開始"
            detail = "按下「我要睡了」後，正式 iOS 版會開始睡後手機活動偵測。"
            icon = "📱"
            badge = "待啟用"
            badge_bg = "#E7E1D8"
        elif active_record:
            status_title = "睡眠模式進行中"
            detail = "已建立睡後偵測工作階段；目前 Flet 預覽版無法讀取 iPhone Screen Time。"
            icon = "🌙"
            badge = "等待 iOS"
            badge_bg = "#F3E9CF"
        elif record.get("post_checkin_screen_minutes") is not None:
            mins = record["post_checkin_screen_minutes"]
            last_time = (
                record["last_phone_activity_time"].strftime("%H:%M")
                if record.get("last_phone_activity_time")
                else "--:--"
            )
            app_name = record.get("last_phone_app") or "系統未提供 App 名稱"
            status_title = f"睡後仍使用 {mins} 分鐘"
            detail = f"最後活動 {last_time} · {app_name}"
            icon = "📱"
            badge = "已有資料"
            badge_bg = ACCENT_LIGHT
        else:
            status_title = "等待 iPhone 使用資料"
            detail = "睡眠紀錄已完成；正式 iOS 版取得授權後會在這裡顯示睡後使用時間。"
            icon = "☁"
            badge = "尚無系統資料"
            badge_bg = "#E7E1D8"

        return card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    t(icon, size=22),
                                    t(
                                        "睡後手機活動",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                spacing=7,
                            ),
                            ft.Container(
                                content=t(
                                    badge,
                                    size=10,
                                    color=TEXT,
                                ),
                                bgcolor=badge_bg,
                                border_radius=12,
                                padding=ft.Padding.symmetric(
                                    horizontal=9,
                                    vertical=5,
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    t(
                        status_title,
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    t(
                        detail,
                        size=12,
                        color=SUBTEXT,
                    ),
                ],
                spacing=7,
            ),
            bgcolor="#FFF9F0",
        )

    # =============================
    # 今日頁
    # =============================
    def build_home():
        now = datetime.now()

        streak_text = t(
            "",
            size=28,
            weight=ft.FontWeight.BOLD,
        )

        best_streak_text = t(
            "",
            size=14,
            color=SUBTEXT,
        )

        duration_text = t(
            "",
            size=35,
            weight=ft.FontWeight.BOLD,
            font_family=DISPLAY_FONT,
        )

        time_text = t(
            "",
            size=15,
            color=SUBTEXT,
        )

        message_text = t(
            "",
            size=14,
            color=SUBTEXT,
        )

        sleep_button = ft.Button(
            content="我要睡了",
            height=64,
            expand=True,
            bgcolor=ACCENT_DARK,
            color="#FFFFFF",
        )

        phone_activity_holder = ft.Column(spacing=0)

        def refresh_values():
            streak = database.get_streak()
            best = database.get_longest_streak()

            streak_text.value = f"{streak} 天"
            best_streak_text.value = f"最長連續紀錄：{best} 天"

            completed = completed_records()

            if completed:
                last = completed[0]

                duration_text.value = (
                    f"{last['hours']} 小時 "
                    f"{last['minutes']:02d} 分"
                )

                time_text.value = (
                    last["sleep_time"].strftime("%H:%M")
                    + "  →  "
                    + last["wake_time"].strftime("%H:%M")
                )
            else:
                duration_text.value = "-- 小時 -- 分"
                time_text.value = "--:--  →  --:--"

            active = database.get_active_sleep()
            today_key = datetime.now().strftime("%Y-%m-%d")
            today_done = database.record_exists_for_date(today_key)

            active_record = None
            if active:
                active_id = active[0]
                active_record = next(
                    (r for r in records_cache if r["id"] == active_id),
                    None,
                )

            last_activity_record = (
                records_cache[0]
                if records_cache
                else None
            )

            phone_activity_holder.controls.clear()
            phone_activity_holder.controls.append(
                build_phone_activity_card(
                    active_record=active_record,
                    last_record=last_activity_record,
                )
            )

            if active:
                sleep_button.content = "☀ 我起床了"
                sleep_button.disabled = False
                sleep_button.bgcolor = BLUE
            elif today_done:
                sleep_button.content = "✓ 今天已完成睡眠紀錄"
                sleep_button.disabled = True
                sleep_button.bgcolor = "#B9B5AD"
            else:
                sleep_button.content = "☾ 我要睡了"
                sleep_button.disabled = False
                sleep_button.bgcolor = ACCENT_DARK

        def button_clicked(e):
            active = database.get_active_sleep()

            if active is None:
                result = database.start_sleep()

                if result["ok"]:
                    database.mark_phone_monitoring_started(
                        result["record_id"]
                    )
                    message_text.value = (
                        "已記錄睡覺時間 "
                        + result["sleep_time"].strftime("%H:%M")
                        + "，睡後手機偵測流程已啟動。"
                    )
                    message_text.color = ACCENT_DARK
                else:
                    message_text.value = "今天已經有睡眠紀錄。"
                    message_text.color = ERROR
            else:
                result = database.wake_up()

                if result:
                    database.mark_phone_monitoring_stopped(
                        result["record_id"]
                    )
                    message_text.value = (
                        f"早安！這晚睡了 "
                        f"{result['hours']} 小時 "
                        f"{result['minutes']} 分鐘。"
                    )
                    message_text.color = ACCENT_DARK

            reload_records()
            refresh_values()
            page.update()

        sleep_button.on_click = button_clicked
        refresh_values()

        return ft.Column(
            [
                header_card(),
                t(
                    now.strftime("%Y / %m / %d"),
                    size=12,
                    color=SUBTEXT,
                ),

                # 睡覺按鈕移到首頁上半部，確保不會被捲到底部而「消失」
                ft.Container(
                    content=ft.Row([sleep_button]),
                    padding=ft.Padding.symmetric(vertical=4),
                ),
                message_text,
                phone_activity_holder,

                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            t(
                                                "連續打卡",
                                                size=13,
                                                color=SUBTEXT,
                                            ),
                                            streak_text,
                                            best_streak_text,
                                        ],
                                        expand=True,
                                    ),
                                    t("🌱", size=34),
                                ]
                            ),
                            ft.Container(height=6),
                            build_streak_visual(),
                        ],
                        spacing=7,
                    ),
                    bgcolor="#FFFDF8",
                ),

                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    t(
                                        "昨晚睡眠",
                                        size=13,
                                        color=SUBTEXT,
                                    ),
                                    t("☁", size=23, color=BLUE),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            duration_text,
                            time_text,
                        ]
                    )
                ),

                bedtime_tip(),
            ],
            spacing=12,
        )

    # =============================
    # 月曆式日誌
    # =============================
    def calendar_cell(day_number, month_dt, record_dates):
        if day_number == 0:
            return ft.Container(height=44, expand=True)

        day_dt = month_dt.replace(day=day_number).date()
        has_record = day_dt in record_dates
        is_today = day_dt == datetime.now().date()

        return ft.Container(
            content=ft.Column(
                [
                    t(
                        str(day_number),
                        size=12,
                        weight=ft.FontWeight.BOLD if is_today else None,
                        color="#FFFFFF" if has_record else TEXT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    t(
                        "✓" if has_record else "",
                        size=9,
                        color="#FFFFFF",
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            height=44,
            expand=True,
            border_radius=14,
            bgcolor=(
                ACCENT_DARK
                if has_record
                else ("#ECDDBC" if is_today else "#EAE4DB")
            ),
            alignment=ft.Alignment.CENTER,
        )

    def build_calendar():
        record_dates = {
            r["sleep_time"].date()
            for r in records_cache
        }

        month_matrix = calendar.monthcalendar(
            journal_month.year,
            journal_month.month,
        )

        def prev_month(e):
            nonlocal journal_month
            first = journal_month.replace(day=1)
            journal_month = (
                first - timedelta(days=1)
            ).replace(day=1)
            show_page(1)

        def next_month(e):
            nonlocal journal_month

            if journal_month.month == 12:
                journal_month = journal_month.replace(
                    year=journal_month.year + 1,
                    month=1,
                    day=1,
                )
            else:
                journal_month = journal_month.replace(
                    month=journal_month.month + 1,
                    day=1,
                )

            show_page(1)

        rows = [
            ft.Row(
                [
                    ft.Container(
                        content=t(
                            weekday,
                            size=10,
                            color=SUBTEXT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    )
                    for weekday in ["一", "二", "三", "四", "五", "六", "日"]
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            )
        ]

        for week in month_matrix:
            rows.append(
                ft.Row(
                    [
                        calendar_cell(
                            day,
                            journal_month,
                            record_dates,
                        )
                        for day in week
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                )
            )

        return card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Button(
                                content="←",
                                on_click=prev_month,
                            ),
                            t(
                                journal_month.strftime("%Y 年 %m 月"),
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Button(
                                content="→",
                                on_click=next_month,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    *rows,
                    t(
                        "深綠色日期代表已有睡眠紀錄。",
                        size=11,
                        color=SUBTEXT,
                    ),
                ],
                spacing=8,
            )
        )

    # =============================
    # 日誌頁
    # =============================
    def build_journal():
        column = ft.Column(spacing=12)

        column.controls.extend([
            ft.Row(
                [
                    ft.Column(
                        [
                            t(
                                "睡眠日誌",
                                size=29,
                                weight=ft.FontWeight.BOLD,
                            ),
                            t(
                                "用月曆查看每一天的睡眠紀錄。",
                                size=13,
                                color=SUBTEXT,
                            ),
                        ],
                        expand=True,
                    ),
                    t("📖", size=30),
                ]
            ),
            build_calendar(),
        ])

        new_date = styled_field(
            label="日期",
            value=datetime.now().strftime("%Y-%m-%d"),
        )

        new_sleep, new_sleep_row = time_field(
            "睡覺時間",
            "23:30",
        )

        new_wake, new_wake_row = time_field(
            "起床時間",
            "07:30",
        )

        new_note = styled_field(
            label="備註",
            hint_text="例如：喝咖啡、運動、考試、心情...",
        )

        error_text = t("", color=ERROR)

        def add_clicked(e):
            try:
                sleep_time, wake_time = parse_sleep_times(
                    new_date.value.strip(),
                    new_sleep.value.strip(),
                    new_wake.value.strip(),
                )

                result = database.add_manual_record(
                    sleep_time,
                    wake_time,
                    new_note.value.strip(),
                )

                if not result["ok"]:
                    error_text.value = (
                        f"{result['sleep_date']} 已經有紀錄，"
                        "一天只能一筆。"
                    )
                    page.update()
                    return

                reload_records()
                show_page(1)

            except ValueError:
                error_text.value = "日期格式請使用 YYYY-MM-DD。"
                page.update()

        column.controls.append(
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                t(
                                    "手動補登",
                                    size=17,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                t("🛏️", size=22),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        new_date,
                        new_sleep_row,
                        new_wake_row,
                        new_note,
                        error_text,
                        ft.Button(
                            content="新增紀錄",
                            on_click=add_clicked,
                        ),
                    ],
                    spacing=10,
                ),
                bgcolor="#FFFDF8",
            )
        )

        month_records = [
            r for r in records_cache
            if (
                r["sleep_time"].year == journal_month.year
                and r["sleep_time"].month == journal_month.month
            )
        ]

        column.controls.append(
            t(
                f"{journal_month.month} 月紀錄",
                size=18,
                weight=ft.FontWeight.BOLD,
            )
        )

        if not month_records:
            column.controls.append(
                card(
                    ft.Row(
                        [
                            t("☁", size=28, color=BLUE),
                            t(
                                "這個月還沒有睡眠紀錄。",
                                color=SUBTEXT,
                            ),
                        ]
                    )
                )
            )
            return column

        for record in month_records:
            sleep_text = record["sleep_time"].strftime("%H:%M")

            if record["wake_time"]:
                wake_text = record["wake_time"].strftime("%H:%M")
                duration = (
                    f"{record['hours']} 小時 "
                    f"{record['minutes']:02d} 分"
                )
            else:
                wake_text = "尚未起床"
                duration = "睡眠進行中"

            edit_area = ft.Column(
                visible=False,
                spacing=8,
            )

            edit_date = styled_field(
                label="日期",
                value=record["sleep_time"].strftime("%Y-%m-%d"),
            )

            edit_sleep, edit_sleep_row = time_field(
                "睡覺時間",
                sleep_text,
            )

            edit_wake, edit_wake_row = time_field(
                "起床時間",
                (
                    record["wake_time"].strftime("%H:%M")
                    if record["wake_time"]
                    else "07:30"
                ),
            )

            edit_note = styled_field(
                label="備註",
                value=record["note"] or "",
            )

            edit_error = t("", color=ERROR)

            delete_confirm = ft.Row(
                visible=False,
                controls=[],
                wrap=True,
                spacing=6,
                run_spacing=6,
            )

            def make_edit(area):
                def clicked(e):
                    area.visible = True
                    page.update()
                return clicked

            def make_cancel(area):
                def clicked(e):
                    area.visible = False
                    page.update()
                return clicked

            def make_save(
                record_id,
                date_field,
                sleep_field,
                wake_field,
                note_field,
                error_field,
            ):
                def clicked(e):
                    try:
                        sleep_dt, wake_dt = parse_sleep_times(
                            date_field.value.strip(),
                            sleep_field.value.strip(),
                            wake_field.value.strip(),
                        )

                        result = database.update_record(
                            record_id,
                            sleep_dt,
                            wake_dt,
                            note_field.value.strip(),
                        )

                        if not result["ok"]:
                            error_field.value = (
                                f"{result['sleep_date']} 已經有另一筆紀錄。"
                            )
                            page.update()
                            return

                        reload_records()
                        show_page(1)

                    except ValueError:
                        error_field.value = "請檢查日期格式。"
                        page.update()

                return clicked

            def make_delete_prompt(area):
                def clicked(e):
                    area.visible = True
                    page.update()
                return clicked

            def make_delete_cancel(area):
                def clicked(e):
                    area.visible = False
                    page.update()
                return clicked

            def make_delete(record_id):
                def clicked(e):
                    database.delete_record(record_id)
                    reload_records()
                    show_page(1)
                return clicked

            edit_button = ft.Button(
                content="編輯",
                on_click=make_edit(edit_area),
            )

            delete_button = ft.Button(
                content="刪除",
                on_click=make_delete_prompt(delete_confirm),
            )

            save_button = ft.Button(
                content="儲存",
                on_click=make_save(
                    record["id"],
                    edit_date,
                    edit_sleep,
                    edit_wake,
                    edit_note,
                    edit_error,
                ),
            )

            cancel_button = ft.Button(
                content="取消",
                on_click=make_cancel(edit_area),
            )

            delete_confirm.controls.extend([
                t(
                    "確定刪除這一天的紀錄？",
                    color=ERROR,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Button(
                    content="確定刪除",
                    on_click=make_delete(record["id"]),
                ),
                ft.Button(
                    content="取消",
                    on_click=make_delete_cancel(delete_confirm),
                ),
            ])

            edit_area.controls.extend([
                edit_date,
                edit_sleep_row,
                edit_wake_row,
                edit_note,
                edit_error,
                ft.Row([save_button, cancel_button], wrap=True, spacing=8),
            ])

            phone_line = ""

            if record["last_phone_activity_time"]:
                phone_line = (
                    "睡後最後手機活動："
                    + record["last_phone_activity_time"].strftime("%H:%M")
                )

                if record["last_phone_app"]:
                    phone_line += f" · {record['last_phone_app']}"

            controls = [
                ft.Row(
                    [
                        t(
                            record["sleep_date"],
                            size=12,
                            color=SUBTEXT,
                        ),
                        t("✓", size=14, color=ACCENT_DARK),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                t(
                    duration,
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    font_family=DISPLAY_FONT,
                ),
                t(
                    f"{sleep_text}  →  {wake_text}",
                    color=SUBTEXT,
                ),
                t(
                    record["note"]
                    if record["note"]
                    else "沒有備註",
                    size=13,
                    color=SUBTEXT,
                ),
            ]

            if phone_line:
                controls.append(
                    t(
                        "📱 " + phone_line,
                        size=12,
                        color=ACCENT_DARK,
                    )
                )

            controls.extend([
                ft.Row([edit_button, delete_button], wrap=True, spacing=8),
                delete_confirm,
                edit_area,
            ])

            column.controls.append(
                card(
                    ft.Column(
                        controls,
                        spacing=7,
                    )
                )
            )

        return column

    # =============================
    # App 內圖表
    # =============================
    def build_sleep_chart(records):
        if not records:
            return t(
                "還沒有圖表資料",
                color=SUBTEXT,
            )

        sorted_records = sorted(
            records,
            key=lambda r: r["sleep_time"],
        )[-7:]

        bars = []

        for record in sorted_records:
            minutes = duration_minutes(record)
            ratio = min(minutes / (12 * 60), 1)
            height = max(int(150 * ratio), 8)

            bars.append(
                ft.Column(
                    [
                        t(
                            f"{record['hours']}時{record['minutes']:02d}分",
                            size=9,
                            color=SUBTEXT,
                        ),
                        ft.Container(
                            width=25,
                            height=height,
                            bgcolor=BLUE,
                            border_radius=10,
                        ),
                        t(
                            record["sleep_time"].strftime("%m/%d"),
                            size=9,
                            color=SUBTEXT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    expand=True,
                )
            )

        return ft.Container(
            content=ft.Row(
                bars,
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            height=210,
            padding=10,
        )

    # =============================
    # 分析頁
    # =============================
    def build_analytics():
        # Flet 1.0.3 的 Dropdown 事件在不同版本表現不一致，
        # 改成三顆明確按鈕，避免 7 天 / 30 天 / 全部 無法切換。
        current_period = {"value": "7"}

        analytics_area = ft.Column(spacing=14)

        btn_7 = ft.Button(content="7 天", expand=True)
        btn_30 = ft.Button(content="30 天", expand=True)
        btn_all = ft.Button(content="全部", expand=True)

        def style_period_buttons():
            selected_bg = ACCENT_DARK
            selected_fg = "#FFFFFF"
            normal_bg = "#EAE4DB"
            normal_fg = TEXT

            for key, button in [
                ("7", btn_7),
                ("30", btn_30),
                ("all", btn_all),
            ]:
                if current_period["value"] == key:
                    button.bgcolor = selected_bg
                    button.color = selected_fg
                else:
                    button.bgcolor = normal_bg
                    button.color = normal_fg

        def get_filtered_records():
            completed = completed_records()

            if current_period["value"] == "7":
                cutoff = datetime.now().date() - timedelta(days=6)
                return [
                    r for r in completed
                    if r["sleep_time"].date() >= cutoff
                ]

            if current_period["value"] == "30":
                cutoff = datetime.now().date() - timedelta(days=29)
                return [
                    r for r in completed
                    if r["sleep_time"].date() >= cutoff
                ]

            return completed

        def refresh_analysis():
            records = get_filtered_records()
            analytics_area.controls.clear()

            if not records:
                analytics_area.controls.append(
                    card(
                        t(
                            "這個期間還沒有睡眠資料。",
                            color=SUBTEXT,
                        )
                    )
                )
                return

            total = sum(duration_minutes(r) for r in records)
            average = int(total / len(records))
            longest = max(records, key=duration_minutes)
            shortest = min(records, key=duration_minutes)

            phone_records = [
                r for r in records
                if r["post_checkin_screen_minutes"] is not None
            ]

            analytics_area.controls.extend([
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    t(
                                        "平均睡眠",
                                        size=12,
                                        color=SUBTEXT,
                                    ),
                                    t(
                                        minutes_to_text(average),
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ]
                            ),
                            bgcolor=CARD,
                            padding=15,
                            border_radius=20,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    t(
                                        "完整紀錄",
                                        size=12,
                                        color=SUBTEXT,
                                    ),
                                    t(
                                        f"{len(records)} 天",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ]
                            ),
                            bgcolor=CARD,
                            padding=15,
                            border_radius=20,
                            expand=True,
                        ),
                    ]
                ),
                card(
                    ft.Column(
                        [
                            t(
                                "平均睡眠時刻",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            t(
                                                "平均入睡",
                                                size=11,
                                                color=SUBTEXT,
                                            ),
                                            t(
                                                average_sleep_clock(records),
                                                size=23,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                    ft.Column(
                                        [
                                            t(
                                                "平均起床",
                                                size=11,
                                                color=SUBTEXT,
                                            ),
                                            t(
                                                average_wake_clock(records),
                                                size=23,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                ]
                            ),
                        ]
                    )
                ),
                card(
                    ft.Column(
                        [
                            t(
                                "最近睡眠趨勢",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            build_sleep_chart(records),
                        ]
                    )
                ),
                card(
                    ft.Column(
                        [
                            t("最長睡眠", size=12, color=SUBTEXT),
                            t(
                                minutes_to_text(
                                    duration_minutes(longest)
                                ),
                                size=21,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(height=7),
                            t("最短睡眠", size=12, color=SUBTEXT),
                            t(
                                minutes_to_text(
                                    duration_minutes(shortest)
                                ),
                                size=21,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ]
                    )
                ),
                card(
                    ft.Column(
                        [
                            t(
                                "睡後手機使用",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            t(
                                (
                                    f"已有 {len(phone_records)} 天取得手機活動資料"
                                    if phone_records
                                    else
                                    "目前尚未取得 iPhone 螢幕使用資料。"
                                ),
                                color=SUBTEXT,
                                size=12,
                            ),
                        ]
                    ),
                    bgcolor="#FFF9F0",
                ),
            ])

        def change_period(value):
            def handler(e):
                current_period["value"] = value
                style_period_buttons()
                refresh_analysis()
                page.update()
            return handler

        btn_7.on_click = change_period("7")
        btn_30.on_click = change_period("30")
        btn_all.on_click = change_period("all")

        style_period_buttons()
        refresh_analysis()

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                t(
                                    "睡眠分析",
                                    size=29,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                t(
                                    "查看近期睡眠變化與平均值。",
                                    size=13,
                                    color=SUBTEXT,
                                ),
                            ],
                            expand=True,
                        ),
                        t("📊", size=29),
                    ]
                ),
                ft.Row(
                    [btn_7, btn_30, btn_all],
                    spacing=6,
                ),
                analytics_area,
            ],
            spacing=10,
        )

    # =============================
    # 匯出
    # =============================
    def ensure_exports():
        os.makedirs("exports", exist_ok=True)

    def export_csv():
        ensure_exports()

        path = os.path.abspath(
            os.path.join(
                "exports",
                f"sleep_records_{datetime.now():%Y%m%d_%H%M%S}.csv",
            )
        )

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.writer(f)

            writer.writerow([
                "日期",
                "睡覺時間",
                "起床時間",
                "睡眠時數",
                "備註",
                "睡後最後手機活動",
                "最後活動 App",
                "睡後螢幕使用分鐘",
            ])

            for r in sorted(
                records_cache,
                key=lambda x: x["sleep_time"],
            ):
                writer.writerow([
                    r["sleep_date"],
                    r["sleep_time"].strftime("%Y-%m-%d %H:%M"),
                    (
                        r["wake_time"].strftime("%Y-%m-%d %H:%M")
                        if r["wake_time"]
                        else ""
                    ),
                    (
                        f"{r['hours']} 小時 {r['minutes']} 分"
                        if r["wake_time"]
                        else "進行中"
                    ),
                    r["note"],
                    (
                        r["last_phone_activity_time"].strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        if r["last_phone_activity_time"]
                        else ""
                    ),
                    r["last_phone_app"],
                    (
                        r["post_checkin_screen_minutes"]
                        if r["post_checkin_screen_minutes"] is not None
                        else ""
                    ),
                ])

        return path

    def export_excel():
        ensure_exports()

        path = os.path.abspath(
            os.path.join(
                "exports",
                f"sleep_records_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            )
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "睡眠紀錄"

        headers = [
            "日期",
            "睡覺時間",
            "起床時間",
            "睡眠時數",
            "備註",
            "睡後最後手機活動",
            "最後活動 App",
            "睡後螢幕使用分鐘",
        ]

        ws.append(headers)

        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        for r in sorted(
            records_cache,
            key=lambda x: x["sleep_time"],
        ):
            ws.append([
                r["sleep_date"],
                r["sleep_time"].strftime("%Y-%m-%d %H:%M"),
                (
                    r["wake_time"].strftime("%Y-%m-%d %H:%M")
                    if r["wake_time"]
                    else ""
                ),
                (
                    f"{r['hours']} 小時 {r['minutes']} 分"
                    if r["wake_time"]
                    else "進行中"
                ),
                r["note"],
                (
                    r["last_phone_activity_time"].strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if r["last_phone_activity_time"]
                    else ""
                ),
                r["last_phone_app"],
                (
                    r["post_checkin_screen_minutes"]
                    if r["post_checkin_screen_minutes"] is not None
                    else ""
                ),
            ])

        widths = {
            "A": 14,
            "B": 20,
            "C": 20,
            "D": 16,
            "E": 32,
            "F": 22,
            "G": 26,
            "H": 18,
        }

        for col, width in widths.items():
            ws.column_dimensions[col].width = width

        wb.save(path)
        return path

    def get_cjk_font():
        candidates = [
            r"C:\Windows\Fonts\msjh.ttc",
            r"C:\Windows\Fonts\msjhbd.ttc",
            r"C:\Windows\Fonts\mingliu.ttc",
            r"C:\Windows\Fonts\kaiu.ttf",
        ]

        for candidate in candidates:
            if os.path.exists(candidate):
                return FontProperties(fname=candidate)

        return FontProperties(family="sans-serif")

    def setup_matplotlib():
        plt.rcParams["axes.unicode_minus"] = False

    def chart_data():
        records = sorted(
            completed_records(),
            key=lambda r: r["sleep_time"],
        )

        return (
            [r["sleep_time"].strftime("%m/%d") for r in records],
            [duration_minutes(r) / 60 for r in records],
        )

    def export_png():
        ensure_exports()

        path = os.path.abspath(
            os.path.join(
                "exports",
                f"sleep_report_{datetime.now():%Y%m%d_%H%M%S}.png",
            )
        )

        return export_a4_sleep_visual(
            records_cache,
            path,
            current_streak=database.get_streak(),
            longest_streak=database.get_longest_streak(),
        )

    def export_pdf():
        ensure_exports()

        path = os.path.abspath(
            os.path.join(
                "exports",
                f"sleep_report_{datetime.now():%Y%m%d_%H%M%S}.pdf",
            )
        )

        return export_a4_sleep_report(
            records_cache,
            path,
            current_streak=database.get_streak(),
            longest_streak=database.get_longest_streak(),
        )

    # =============================
    # 設定頁
    # =============================
    def build_settings():
        export_message = t(
            "",
            size=11,
            color=SUBTEXT,
            selectable=True,
        )

        share_message = t(
            "",
            size=11,
            color=SUBTEXT,
            selectable=True,
        )

        def run_export(exporter, label):
            try:
                path = exporter()
                export_message.value = f"{label} 已匯出：\n{path}"
                export_message.color = ACCENT_DARK
            except Exception as exc:
                export_message.value = f"{label} 匯出失敗：{exc}"
                export_message.color = ERROR

            page.update()

        def _build_share_bytes(kind):
            """
            先在 Python 端產生報告，再讀成 bytes 傳給 iPhone 分享面板。
            這樣不會把 Windows 的 C:\\... 路徑交給 iPhone。
            """
            suffix = ".png" if kind == "png" else ".pdf"

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(
                    temp_dir,
                    f"sleep_report_{datetime.now():%Y%m%d_%H%M%S}{suffix}",
                )

                export_a4_sleep_visual(
                    records_cache,
                    temp_path,
                    current_streak=database.get_streak(),
                    longest_streak=database.get_longest_streak(),
                )

                with open(temp_path, "rb") as f:
                    return f.read()

        async def share_png(e):
            share_message.value = "正在準備 PNG 報告…"
            share_message.color = SUBTEXT
            page.update()

            try:
                data = _build_share_bytes("png")
                name = f"睡眠日記_{datetime.now():%Y%m%d}.png"

                file = ft.ShareFile.from_bytes(
                    data,
                    mime_type="image/png",
                    name=name,
                )

                await share_service.share_files(
                    [file],
                    title="分享睡眠日記",
                    text="我的睡眠日記",
                )

                share_message.value = (
                    "已開啟 iPhone 分享選單。"
                    "要放進相簿請選「儲存影像」。"
                )
                share_message.color = ACCENT_DARK

            except Exception as exc:
                share_message.value = f"PNG 分享失敗：{exc}"
                share_message.color = ERROR

            page.update()

        async def share_pdf(e):
            share_message.value = "正在準備 PDF 報告…"
            share_message.color = SUBTEXT
            page.update()

            try:
                data = _build_share_bytes("pdf")
                name = f"睡眠日記_{datetime.now():%Y%m%d}.pdf"

                file = ft.ShareFile.from_bytes(
                    data,
                    mime_type="application/pdf",
                    name=name,
                )

                await share_service.share_files(
                    [file],
                    title="分享睡眠報告",
                    text="我的睡眠日記 PDF 報告",
                )

                share_message.value = (
                    "已開啟分享選單。"
                    "PDF 可存到「檔案」、AirDrop 或傳到其他 App。"
                )
                share_message.color = ACCENT_DARK

            except Exception as exc:
                share_message.value = f"PDF 分享失敗：{exc}"
                share_message.color = ERROR

            page.update()

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                t(
                                    "設定",
                                    size=29,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                t(
                                    "匯出、分享與 iPhone 功能。",
                                    size=13,
                                    color=SUBTEXT,
                                ),
                            ],
                            expand=True,
                        ),
                        t("⚙️", size=29),
                    ]
                ),

                # -----------------
                # iPhone 優先操作
                # -----------------
                card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            t(
                                                "iPhone 分享",
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            t(
                                                "使用 iOS 原生分享選單。",
                                                size=12,
                                                color=SUBTEXT,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                    t("📱", size=25),
                                ]
                            ),

                            ft.Row(
                                [
                                    ft.Button(
                                        content="分享 PNG",
                                        icon=ft.Icons.SHARE,
                                        on_click=share_png,
                                        expand=True,
                                    ),
                                    ft.Button(
                                        content="分享 PDF",
                                        icon=ft.Icons.SHARE,
                                        on_click=share_pdf,
                                        expand=True,
                                    ),
                                ],
                                spacing=8,
                            ),

                            ft.Container(
                                content=ft.Row(
                                    [
                                        t("🖼️", size=20),
                                        t(
                                            "PNG：在 iPhone 分享選單點「儲存影像」"
                                            "即可放進照片 App。",
                                            size=12,
                                            color=SUBTEXT,
                                            expand=True,
                                        ),
                                    ],
                                    vertical_alignment=(
                                        ft.CrossAxisAlignment.CENTER
                                    ),
                                ),
                                bgcolor="#F3EEE5",
                                border_radius=16,
                                padding=12,
                            ),

                            share_message,
                        ],
                        spacing=10,
                    ),
                    bgcolor="#FFF9F0",
                ),

                # -----------------
                # Windows / 桌面匯出
                # -----------------
                card(
                    ft.Column(
                        [
                            t(
                                "檔案匯出",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            t(
                                "Windows 測試時仍可匯出到 exports 資料夾。",
                                color=SUBTEXT,
                            ),
                            ft.Row(
                                [
                                    ft.Button(
                                        content="CSV",
                                        on_click=lambda e: run_export(
                                            export_csv,
                                            "CSV",
                                        ),
                                    ),
                                    ft.Button(
                                        content="Excel",
                                        on_click=lambda e: run_export(
                                            export_excel,
                                            "Excel",
                                        ),
                                    ),
                                ],
                                wrap=True,
                                spacing=8,
                                run_spacing=8,
                            ),
                            ft.Row(
                                [
                                    ft.Button(
                                        content="PDF",
                                        on_click=lambda e: run_export(
                                            export_pdf,
                                            "PDF",
                                        ),
                                    ),
                                    ft.Button(
                                        content="PNG",
                                        on_click=lambda e: run_export(
                                            export_png,
                                            "PNG",
                                        ),
                                    ),
                                ],
                                wrap=True,
                                spacing=8,
                                run_spacing=8,
                            ),
                            export_message,
                        ],
                        spacing=10,
                    )
                ),

                card(
                    ft.Column(
                        [
                            t(
                                "睡後手機偵測",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            t(
                                "下一階段會把「我要睡了」接到 iOS "
                                "Screen Time / Device Activity。",
                                color=SUBTEXT,
                                size=12,
                            ),
                            t(
                                "目前先完成分享與相簿流程；"
                                "手機使用偵測需要正式 iOS 原生權限與 extension。",
                                color=ACCENT_DARK,
                                size=12,
                            ),
                        ],
                        spacing=7,
                    ),
                    bgcolor="#FFF9F0",
                ),

                card(
                    ft.Row(
                        [
                            t("🐑", size=32),
                            ft.Column(
                                [
                                    t(
                                        "睡眠日記 v1.3",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    t(
                                        "睡後手機偵測流程骨架",
                                        size=12,
                                        color=SUBTEXT,
                                    ),
                                ],
                                expand=True,
                            ),
                            t("☾", size=27, color=YELLOW),
                        ]
                    )
                ),
            ],
            spacing=14,
        )

    # =============================
    # 換頁
    # =============================
    def show_page(index):
        content_area.controls.clear()

        if index == 0:
            content_area.controls.append(build_home())
        elif index == 1:
            content_area.controls.append(build_journal())
        elif index == 2:
            content_area.controls.append(build_analytics())
        else:
            content_area.controls.append(build_settings())

        navigation.selected_index = index
        page.update()

    def nav_changed(e):
        show_page(e.control.selected_index)

    navigation = ft.NavigationBar(
        selected_index=0,
        on_change=nav_changed,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME,
                label="今日",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.CALENDAR_MONTH,
                label="日誌",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART,
                label="分析",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS,
                label="設定",
            ),
        ],
    )

    page.add(
        ft.Column(
            [
                content_area,
                navigation,
            ],
            expand=True,
        )
    )

    show_page(0)


if __name__ == "__main__":
    ft.run(main)

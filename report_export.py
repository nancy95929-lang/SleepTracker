from __future__ import annotations

import os
import math
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.font_manager import FontProperties


BG = "#F7F2EA"
CARD = "#FFFDFC"
TEXT = "#2D312E"
SUBTEXT = "#565C56"
ACCENT = "#789276"
ACCENT_DARK = "#566D58"
ACCENT_LIGHT = "#DDE7DA"
BLUE = "#8DA8BB"
PINK = "#D6AAA5"
GOLD = "#D7B765"
LINE = "#D9D2C8"


def _font_properties(bold=False):
    candidates = [
        r"C:\Windows\Fonts\msjhbd.ttc" if bold else r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjh.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return FontProperties(fname=candidate)

    return FontProperties(family="sans-serif", weight="bold" if bold else "normal")


def _minutes(record):
    return int(record["hours"]) * 60 + int(record["minutes"])


def _minutes_text(total_minutes):
    return f"{total_minutes // 60} 小時 {total_minutes % 60:02d} 分"


def _average_sleep_clock(records):
    if not records:
        return "--:--"

    values = []
    for record in records:
        sleep = record["sleep_time"]
        value = sleep.hour * 60 + sleep.minute
        if sleep.hour < 12:
            value += 24 * 60
        values.append(value)

    avg = int(sum(values) / len(values)) % (24 * 60)
    return f"{avg // 60:02d}:{avg % 60:02d}"


def _average_wake_clock(records):
    if not records:
        return "--:--"

    values = [
        record["wake_time"].hour * 60 + record["wake_time"].minute
        for record in records
    ]
    avg = int(sum(values) / len(values))
    return f"{avg // 60:02d}:{avg % 60:02d}"


def _rounded_card(fig, x, y, w, h, facecolor=CARD, radius=0.018, zorder=1):
    patch = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.008,rounding_size={radius}",
        transform=fig.transFigure,
        linewidth=0,
        facecolor=facecolor,
        zorder=zorder,
    )
    fig.patches.append(patch)


def _draw_moon(fig, x, y, r):
    fig.patches.append(
        patches.Circle(
            (x, y),
            r,
            transform=fig.transFigure,
            facecolor="#F0CE7A",
            edgecolor="none",
            zorder=8,
        )
    )
    fig.patches.append(
        patches.Circle(
            (x + r * 0.42, y + r * 0.20),
            r * 0.88,
            transform=fig.transFigure,
            facecolor=BG,
            edgecolor="none",
            zorder=9,
        )
    )


def _draw_cloud(fig, x, y, scale=1.0):
    color = "#DCE5EB"
    for dx, dy, rr in [
        (0.00, 0.00, 0.013),
        (0.018, 0.006, 0.017),
        (0.038, 0.000, 0.014),
        (0.022, -0.006, 0.020),
    ]:
        fig.patches.append(
            patches.Circle(
                (x + dx * scale, y + dy * scale),
                rr * scale,
                transform=fig.transFigure,
                facecolor=color,
                edgecolor="none",
                zorder=7,
            )
        )


def _draw_star(fig, x, y, size=0.010):
    points = []
    for i in range(8):
        angle = math.pi / 4 * i
        radius = size if i % 2 == 0 else size * 0.28
        points.append(
            (
                x + math.cos(angle) * radius,
                y + math.sin(angle) * radius,
            )
        )

    fig.patches.append(
        patches.Polygon(
            points,
            closed=True,
            transform=fig.transFigure,
            facecolor=GOLD,
            edgecolor="none",
            zorder=12,
        )
    )


def export_a4_sleep_report(
    records,
    output_path,
    current_streak=0,
    longest_streak=0,
):
    """向下相容：預設輸出 A4 PDF。"""
    return export_a4_sleep_visual(
        records,
        output_path,
        current_streak=current_streak,
        longest_streak=longest_streak,
    )


def export_a4_sleep_visual(
    records,
    output_path,
    current_streak=0,
    longest_streak=0,
):
    """
    依副檔名輸出單頁 A4 視覺報告。
    支援 .pdf 與 .png，兩者版型完全一致。
    """
    completed = [
        r for r in records
        if r.get("wake_time") is not None
        and r.get("hours") is not None
        and r.get("minutes") is not None
    ]
    completed = sorted(completed, key=lambda r: r["sleep_time"])

    fp = _font_properties(False)
    fp_bold = _font_properties(True)

    fig = plt.figure(figsize=(8.27, 11.69), facecolor=BG)

    _draw_moon(fig, 0.865, 0.934, 0.028)
    _draw_cloud(fig, 0.785, 0.905, 1.0)
    _draw_star(fig, 0.925, 0.900, 0.010)
    _draw_star(fig, 0.750, 0.952, 0.008)

    fig.text(
        0.075,
        0.935,
        "睡眠日記",
        fontproperties=fp_bold,
        fontsize=26,
        color=TEXT,
        va="center",
    )
    fig.text(
        0.075,
        0.901,
        "一頁看懂近期睡眠節奏",
        fontproperties=fp,
        fontsize=10.5,
        color=SUBTEXT,
    )
    fig.text(
        0.925,
        0.860,
        f"報告日期  {datetime.now():%Y / %m / %d}",
        fontproperties=fp,
        fontsize=8.5,
        color=SUBTEXT,
        ha="right",
    )

    if completed:
        avg_minutes = int(sum(_minutes(r) for r in completed) / len(completed))
        avg_sleep = _average_sleep_clock(completed)
        avg_wake = _average_wake_clock(completed)
    else:
        avg_minutes = 0
        avg_sleep = "--:--"
        avg_wake = "--:--"

    card_y = 0.770
    card_h = 0.095
    gap = 0.014
    left = 0.075
    total_w = 0.85
    card_w = (total_w - gap * 3) / 4

    summaries = [
        ("平均睡眠", _minutes_text(avg_minutes) if completed else "尚無資料", ACCENT_LIGHT),
        ("平均入睡", avg_sleep, "#F7E7E4"),
        ("平均起床", avg_wake, "#E6EEF4"),
        ("連續打卡", f"{current_streak} 天", "#F3E9CF"),
    ]

    for i, (label, value, bg) in enumerate(summaries):
        x = left + i * (card_w + gap)
        _rounded_card(fig, x, card_y, card_w, card_h, facecolor=bg, radius=0.018)
        fig.text(
            x + 0.015,
            card_y + 0.064,
            label,
            fontproperties=fp,
            fontsize=8.5,
            color=SUBTEXT,
        )
        fig.text(
            x + 0.015,
            card_y + 0.027,
            value,
            fontproperties=fp_bold,
            fontsize=14.5 if i != 0 else 12.5,
            color=TEXT,
        )

    _rounded_card(fig, 0.075, 0.435, 0.85, 0.300, facecolor=CARD, radius=0.022)

    fig.text(
        0.10,
        0.700,
        "近期睡眠趨勢",
        fontproperties=fp_bold,
        fontsize=13,
        color=TEXT,
    )
    fig.text(
        0.10,
        0.678,
        "最近 7 筆完整紀錄",
        fontproperties=fp,
        fontsize=8.5,
        color=SUBTEXT,
    )

    chart_records = completed[-7:]
    ax = fig.add_axes([0.115, 0.485, 0.77, 0.165], facecolor=CARD)
    ax.set_zorder(5)

    if chart_records:
        labels = [r["sleep_time"].strftime("%m/%d") for r in chart_records]
        hours = [_minutes(r) / 60 for r in chart_records]

        bars = ax.bar(labels, hours, width=0.55, color=BLUE)

        for bar, record in zip(bars, chart_records):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.12,
                f"{record['hours']}:{record['minutes']:02d}",
                ha="center",
                va="bottom",
                fontsize=7.8,
                color=SUBTEXT,
                fontproperties=fp,
            )

        average_hours = sum(hours) / len(hours)
        ax.axhline(
            average_hours,
            color=ACCENT,
            linewidth=1.3,
            linestyle=(0, (4, 3)),
        )

        ax.text(
            0.99,
            average_hours + 0.10,
            f"平均 {average_hours:.1f} 小時",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            color=ACCENT_DARK,
            fontsize=7.5,
            fontproperties=fp,
        )

        ymax = max(10, max(hours) + 1.4)
        ax.set_ylim(0, ymax)
    else:
        ax.text(
            0.5,
            0.5,
            "目前還沒有完整睡眠紀錄",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=SUBTEXT,
            fontsize=10,
            fontproperties=fp,
        )
        ax.set_ylim(0, 10)

    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.grid(axis="y", color=LINE, linewidth=0.7, alpha=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0, labelsize=8, colors=SUBTEXT)
    ax.tick_params(axis="y", length=0, labelsize=7, colors=SUBTEXT)
    ax.set_yticks([0, 4, 8])
    ax.set_yticklabels(["0", "4 小時", "8 小時"], fontproperties=fp)

    for label in ax.get_xticklabels():
        label.set_fontproperties(fp)

    _rounded_card(fig, 0.075, 0.305, 0.85, 0.095, facecolor="#FFF9EF", radius=0.020)
    fig.text(
        0.10,
        0.367,
        "連續打卡",
        fontproperties=fp_bold,
        fontsize=11.5,
        color=TEXT,
    )
    fig.text(
        0.815,
        0.367,
        f"最長 {longest_streak} 天",
        fontproperties=fp,
        fontsize=8.5,
        color=SUBTEXT,
        ha="right",
    )

    completed_dates = {r["sleep_time"].date() for r in completed}
    today = datetime.now().date()
    start_x = 0.105
    dot_y = 0.332
    spacing = 0.055

    for i in range(14):
        day = today.fromordinal(today.toordinal() - (13 - i))
        hit = day in completed_dates

        fig.patches.append(
            patches.Circle(
                (start_x + i * spacing, dot_y),
                0.012,
                transform=fig.transFigure,
                facecolor=ACCENT_DARK if hit else "#E4DED5",
                edgecolor="none",
                zorder=8,
            )
        )

        fig.text(
            start_x + i * spacing,
            0.309,
            day.strftime("%d"),
            fontproperties=fp,
            fontsize=6.5,
            color=SUBTEXT,
            ha="center",
        )

    _rounded_card(fig, 0.075, 0.090, 0.85, 0.180, facecolor=CARD, radius=0.020)
    fig.text(
        0.10,
        0.235,
        "最近紀錄",
        fontproperties=fp_bold,
        fontsize=11.5,
        color=TEXT,
    )

    recent = list(reversed(completed[-5:]))

    if recent:
        y = 0.205

        for idx, r in enumerate(recent):
            if idx > 0:
                fig.lines.append(
                    plt.Line2D(
                        [0.10, 0.90],
                        [y + 0.015, y + 0.015],
                        transform=fig.transFigure,
                        color="#E8E2D9",
                        linewidth=0.6,
                    )
                )

            fig.text(
                0.105,
                y,
                r["sleep_time"].strftime("%m/%d"),
                fontproperties=fp_bold,
                fontsize=8.3,
                color=TEXT,
                va="center",
            )
            fig.text(
                0.200,
                y,
                f"{r['sleep_time']:%H:%M} → {r['wake_time']:%H:%M}",
                fontproperties=fp,
                fontsize=8.0,
                color=SUBTEXT,
                va="center",
            )
            fig.text(
                0.485,
                y,
                _minutes_text(_minutes(r)),
                fontproperties=fp_bold,
                fontsize=8.3,
                color=TEXT,
                va="center",
            )

            note = (r.get("note") or "").strip()
            if len(note) > 15:
                note = note[:15] + "…"

            fig.text(
                0.690,
                y,
                note if note else "無備註",
                fontproperties=fp,
                fontsize=7.7,
                color=SUBTEXT,
                va="center",
            )

            y -= 0.027
    else:
        fig.text(
            0.10,
            0.170,
            "目前還沒有完整睡眠紀錄。",
            fontproperties=fp,
            fontsize=9,
            color=SUBTEXT,
        )

    fig.text(
        0.075,
        0.045,
        "睡眠日記 · 把每天的晚安，慢慢變成規律。",
        fontproperties=fp,
        fontsize=7.8,
        color=SUBTEXT,
    )
    _draw_star(fig, 0.912, 0.050, 0.007)

    suffix = Path(output_path).suffix.lower()
    save_kwargs = dict(facecolor=fig.get_facecolor(), bbox_inches=None)

    if suffix == ".png":
        fig.savefig(output_path, format="png", dpi=220, **save_kwargs)
    else:
        fig.savefig(output_path, format="pdf", **save_kwargs)

    plt.close(fig)
    return str(Path(output_path).resolve())

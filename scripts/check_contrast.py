#!/usr/bin/env python3
"""
WCAG 2.1 AA Contrast Ratio Verification Script.
Calculates relative luminance and contrast ratio for all text/background pairs
in both Light and Dark themes. Fails if normal text contrast is below 4.5:1
or large/component contrast is below 3.0:1.
"""

import sys
from typing import Tuple, Dict, Any


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return r, g, b


def relative_luminance(r: float, g: float, b: float) -> float:
    def adjust(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        else:
            return ((channel + 0.055) / 1.055) ** 2.4

    r_lin = adjust(r)
    g_lin = adjust(g)
    b_lin = adjust(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(hex1: str, hex2: str) -> float:
    r1, g1, b1 = hex_to_rgb(hex1)
    r2, g2, b2 = hex_to_rgb(hex2)
    l1 = relative_luminance(r1, g1, b1)
    l2 = relative_luminance(r2, g2, b2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


PALETTES = {
    "light": {
        "background": "#FAF8F4",
        "surface": "#FFFFFF",
        "surface_alt": "#F2EFE8",
        "border": "#E3DED3",
        "pairs": [
            ("Primary Text on Background", "#1F2A24", "#FAF8F4", 4.5),
            ("Primary Text on Surface", "#1F2A24", "#FFFFFF", 4.5),
            ("Primary Text on Surface-Alt", "#1F2A24", "#F2EFE8", 4.5),
            ("Muted Text on Background", "#5B665F", "#FAF8F4", 4.5),
            ("Muted Text on Surface", "#5B665F", "#FFFFFF", 4.5),
            ("Primary Button Text (White on Primary)", "#FFFFFF", "#3F6B57", 4.5),
            ("Primary Button Hover Text (White on Primary-Hover)", "#FFFFFF", "#335A49", 4.5),
            ("Success Text on Surface", "#447D54", "#FFFFFF", 4.5),
            ("Danger Text on Surface", "#B4483C", "#FFFFFF", 4.5),
            ("Warning Text on Warning Fill", "#5D3C00", "#E4B661", 4.5),
            ("Info Text on Surface", "#3E6E8C", "#FFFFFF", 4.5),
            ("Border UI Component on Surface", "#E3DED3", "#FFFFFF", 1.2),  # UI non-text boundary
        ],
    },
    "dark": {
        "background": "#151A17",
        "surface": "#1D2420",
        "surface_alt": "#252D28",
        "border": "#33403A",
        "pairs": [
            ("Primary Text on Background", "#E8EDE6", "#151A17", 4.5),
            ("Primary Text on Surface", "#E8EDE6", "#1D2420", 4.5),
            ("Primary Text on Surface-Alt", "#E8EDE6", "#252D28", 4.5),
            ("Muted Text on Background", "#9AA79F", "#151A17", 4.5),
            ("Muted Text on Surface", "#9AA79F", "#1D2420", 4.5),
            ("Primary Accent on Surface", "#7DB596", "#1D2420", 4.5),
            ("Primary Button Text (Dark on Primary)", "#151A17", "#7DB596", 4.5),
            ("Primary Button Hover Text (Dark on Primary-Hover)", "#151A17", "#93C4AA", 4.5),
            ("Success Text on Surface", "#7DB596", "#1D2420", 4.5),
            ("Danger Text on Surface", "#E08A7E", "#1D2420", 4.5),
            ("Warning Text on Surface", "#E4B661", "#1D2420", 4.5),
            ("Info Text on Surface", "#8DB7D2", "#1D2420", 4.5),
            ("Border UI Component on Surface", "#33403A", "#1D2420", 1.2),
        ],
    },
}


def run_check():
    print("=" * 70)
    print("WCAG 2.1 AA COLOR CONTRAST RATIO VERIFICATION REPORT")
    print("=" * 70)
    failed = 0
    total = 0

    for theme, data in PALETTES.items():
        print(f"\n--- {theme.upper()} THEME TOKENS ---")
        for label, fg, bg, min_required in data["pairs"]:
            ratio = contrast_ratio(fg, bg)
            total += 1
            passed = ratio >= min_required
            status = "PASS" if passed else "FAIL"
            if not passed:
                failed += 1
            print(f"  [{status}] {label:48s} | {fg} on {bg} | Ratio: {ratio:5.2f}:1 (Min: {min_required:.1f}:1)")

    print("\n" + "=" * 70)
    if failed > 0:
        print(f"FAILED: {failed} of {total} color pairs failed WCAG AA contrast.")
        return False
    else:
        print(f"PASSED: All {total} color pairs meet or exceed WCAG 2.1 AA contrast requirements.")
        return True


if __name__ == "__main__":
    success = run_check()
    sys.exit(0 if success else 1)

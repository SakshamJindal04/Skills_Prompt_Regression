# RegGuard Light-Only Modern Design System Specification

**Version:** 2.1 (Light-Only Modern Restyle)  
**Target Environment:** Streamlit Enterprise Dashboard (`ui-light` branch)  
**Streamlit Version Pinned:** `streamlit==1.66.1` (Python 3.12.14)  
**Standard Compliance:** WCAG 2.1 AAA (>= 7.0:1 for Body Text), WCAG 2.1 AA (>= 4.5:1 for Actions & Status), Section 508

---

## 1. Design Philosophy & Architectural Principles

1. **Light-Only Modern Clarity:**
   All backgrounds remain clean and light across operating-system modes. Dark mode code and media queries have been removed. `:root { color-scheme: light; }` and `.streamlit/config.toml` (`base = "light"`) guarantee that operating systems with dark mode enabled render identical, pristine light surfaces.
2. **Text Clarity Above All:**
   No low-contrast gray text anywhere. Primary body text achieves >= 13.0:1 contrast on all surfaces; secondary and caption text achieves >= 7.0:1 on card surfaces. Minimum font sizes are strictly enforced: body >= 16px, table text >= 14px, captions >= 13px. Prose width is capped at 75 characters (`max-width: 75ch`).
3. **Local-First & Zero Runtime Network Dependencies:**
   Zero external web fonts, zero CDN links, and zero telemetry. Native system font stacks and Streamlit bundled Material icons (`:material/...`) provide instant, offline-capable rendering.
4. **Calm Action & Status Hierarchy:**
   Action buttons use light tinted fills with crisp borders and deep high-contrast text rather than heavy saturated blocks. Primary action: `#DBEAFE` fill, `#93C5FD` border, `#1E3A8A` text. Status indicators are always dual-encoded with a Material icon and text label.

---

## 2. Design Tokens & Palette

### Color Tokens

| Token Name | Hex Code | Role & Usage | Contrast vs Background |
| :--- | :--- | :--- | :--- |
| `--arm-bg` | `#F6F8FB` | Page Canvas Background | Base canvas |
| `--arm-surface` | `#FFFFFF` | Card, Container, Sidebar Surface | Base surface |
| `--arm-surface-alt` | `#F1F5F9` | Table Headers, Segmented Tabs, Mono Pills | 1.23:1 boundary |
| `--arm-border` | `#E2E8F0` | Default Structural Card Border (1px) | 1.23:1 boundary |
| `--arm-border-strong` | `#CBD5E1` | Input, Hover, and Empty State Borders | 1.54:1 boundary |
| `--arm-text` | `#1E293B` | Primary Body Text, Headings, KPI Values | **14.63:1** (AAA) |
| `--arm-text-secondary` | `#475569` | Subtitles, Captions, Metric Labels | **7.58:1** (AAA) |
| `--arm-text-muted` | `#475569` | Meta timestamps, audit IDs, guidance | **7.58:1** (AAA) |

### Action Button Tokens

| Action Level | Fill Color | Border Color | Text Color | Hover Fill | Contrast |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Action** | `#DBEAFE` | `#93C5FD` | `#1E3A8A` | `#BFDBFE` | **8.49:1** (AA) |
| **Secondary Action** | `#FFFFFF` | `#CBD5E1` | `#1E293B` | `#F1F5F9` | **14.63:1** (AAA) |
| **Quiet Secondary** | `transparent` | `transparent` | `#475569` | `#F1F5F9` | **7.58:1** (AAA) |

### Status Indicators (Dual-Encoded: Icon + Label)

| Status | Fill Color | Border Color | Text Color | Default Material Icon | Contrast Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PROMOTE / FIXED** | `#DCFCE7` | `#86EFAC` | `#166534` | `:material/check_circle:` | **6.49:1** (AA) |
| **BLOCK / REGRESSED** | `#FEE2E2` | `#FCA5A5` | `#991B1B` | `:material/block:` | **6.80:1** (AA) |
| **WARNING / INCONCLUSIVE**| `#FEF3C7` | `#FCD34D` | `#92400E` | `:material/warning:` | **6.37:1** (AA) |
| **INFO / ADVISORY** | `#E0F2FE` | `#7DD3FC` | `#075985` | `:material/info:` | **6.59:1** (AA) |
| **NEUTRAL / UNCHANGED** | `#F1F5F9` | `#CBD5E1` | `#334155` | `:material/radio_button_unchecked:` | **9.45:1** (AAA) |

### Geometry & Shadows

- **Card Radius:** `12px` (`border-radius: 12px;`)
- **Button / Input Radius:** `8px` (`border-radius: 8px;`)
- **Pill Radius:** `9999px` (`border-radius: 9999px;`)
- **Shadow Scale:** No heavier than `0 1px 2px rgba(15, 23, 42, 0.06)`
- **Content Width:** Constrained to `1280px` centered on viewport.

---

## 3. Typography Hierarchy

- **System Font Stack:** `system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Monospace Stack:** `ui-monospace, "Cascadia Mono", Consolas, monospace`
- **Numerical Alignment:** `font-variant-numeric: tabular-nums` globally enforced.

| Element | Size | Weight | Line Height | Color | Reading Width |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Page Title** (`h1`) | 28 px | 600 | 1.25 | `#1E293B` | Full container |
| **Section Title** (`h2`) | 20 px | 600 | 1.35 | `#1E293B` | Full container |
| **Card Subtitle** (`h3`) | 17 px | 600 | 1.40 | `#1E293B` | Full container |
| **Body Text** (`p`, `li`) | 16 px | 400 | 1.55 | `#1E293B` | Max 75 characters (`75ch`) |
| **Table Cells** (`td`, `th`)| 14 px | 400 / 600 | 1.40 | `#1E293B` | Right-aligned numbers |
| **Captions & Provenance** | 13.5 px | 400 (italic)| 1.45 | `#475569` | Max 75 characters |
| **Monospace / Hashes** | 13.5 px | 500 | 1.30 | `#1E293B` | Tabular numbers |

---

## 4. Plotly Chart Visualization Specification

Registered template: `regguard_light` (aliased to `regguard_natural` and `arm_enterprise`).
- **Paper & Plot Canvas:** Pure white `#FFFFFF`.
- **Gridlines:** Subtle `#E2E8F0` (1px width).
- **Axis Text:** High-contrast dark `#334155` (10.35:1 contrast against white).
- **Sequential Colorway (All >= 3.0:1 contrast against `#FFFFFF`):**
  1. Series 1 (Blue): `#3B82F6` (3.68:1)
  2. Series 2 (Emerald Green): `#059669` (3.77:1)
  3. Series 3 (Dark Amber): `#D97706` (3.19:1)
  4. Series 4 (Crimson Red): `#EF4444` (3.76:1)
  5. Series 5 (Violet): `#8B5CF6` (4.23:1)
  6. Series 6 (Slate): `#64748B` (4.76:1)
- **Legends:** Horizontal top legend positioned at `y = 1.02, x = 1` to prevent visual collision with data curves.

---

## 5. Interaction & Motion Standards

1. **Subtle Transitions:** 150 ms ease-out on hover, focus, buttons, tabs, expanders, and cards. Only applied to non-layout properties (`color`, `border-color`, `background-color`, `box-shadow`).
2. **Keyboard Focus Ring:** 2 px solid `#3B82F6` with 2 px offset (`outline: 2px solid #3B82F6 !important; outline-offset: 2px !important;`).
3. **Accessibility Override:** `@media (prefers-reduced-motion: reduce)` disables all animations and transitions to zero duration.
4. **Progress & Modals:**
   - Destructive actions (Rollback, Promote, Reject) use modal dialogs (`@st.dialog`).
   - Long-running evaluations use `st.status` with live step text and real progress counters.

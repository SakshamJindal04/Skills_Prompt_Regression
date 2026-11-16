# RegGuard Natural Design System Style Guide

**Document Version:** 1.0.0  
**Target Environment:** Local-first Streamlit Dashboard  
**Pinned Streamlit Version:** `streamlit==1.66.1`  
**Accessibility Target:** WCAG 2.1 AA Compliance ($\ge 4.5:1$ Normal Text, $\ge 3.0:1$ Large Text & UI Components)

---

## 1. Design Philosophy & Guardrails

The RegGuard Natural Design System replaces high-saturation, generic enterprise blues with an organic, calm palette inspired by natural sage greens, slate blues, warm ochres, and terracottas.

### Strict Core Principles
1. **Local-First Delivery**: Zero runtime calls to external CDNs, Google Fonts, remote stylesheets, or third-party tracking scripts. All typography relies on local system font stacks; all icons are rendered using Streamlit's built-in Material Symbols (`:material/...`).
2. **Deterministic Data Integrity**: Strict separation between presentation and business logic. Zero modifications to statistical evaluation formulas, gate policies, database models, or raw numerical measurements.
3. **No Colour-Alone Indicators**: Every operational status (verdict, diff status, test result) must be dual-encoded with an explicit textual label and a distinct icon (`PROMOTE`, `BLOCK`, `REGRESSED`, `FIXED`, `INCONCLUSIVE`).
4. **Transparent Data Sourcing**: Every chart, heatmap, and tabular data view must include an italic `.arm-source-caption` directly beneath it stating where the underlying data originates.
5. **Graceful CSS Degradation**: Styling targets stable `.streamlit/config.toml` properties, container keys (`st-key-*`), and standard `data-testid` selectors. If a custom selector fails, the application degrades gracefully to default Streamlit styling without breaking layout.

---

## 2. Natural Color Palette & Design Tokens

### Token Definitions

| Token Name | Light Theme Hex | Dark Theme Hex | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--arm-bg` | `#FAF8F4` | `#151A17` | Canvas root background |
| `--arm-surface` | `#FFFFFF` | `#1D2420` | Primary cards, table background |
| `--arm-surface-alt` | `#F2EFE8` | `#252D28` | Secondary cards, table headers, code blocks |
| `--arm-border` | `#E3DED3` | `#33403A` | Card borders, dividers, table gridlines |
| `--arm-text` | `#1F2A24` | `#E8EDE6` | High-emphasis body text and headers |
| `--arm-text-muted` | `#5B665F` | `#9AA79F` | Secondary labels, descriptions, captions |
| `--arm-text-caption` | `#7A857E` | `#829088` | Small captions and metadata timestamps |
| `--arm-primary` | `#3F6B57` | `#7DB596` | Primary buttons, active tabs, focus outlines |
| `--arm-primary-hover` | `#335A49` | `#6CA485` | Primary button hover state |
| `--arm-success-bg` | `#F0F7F2` | `#1C2A20` | Promotion banner background, pass chips |
| `--arm-success-text` | `#447D54` | `#7DB596` | Success text (calibrated $\ge 4.5:1$ contrast) |
| `--arm-danger-bg` | `#FDF2F0` | `#2C1D1B` | Block banner background, regression chips |
| `--arm-danger-text` | `#B4483C` | `#E08A7E` | Regression text ($\ge 5.3:1$ contrast) |
| `--arm-warning-bg` | `#FEF9EE` | `#2A2416` | Inconclusive banner background, alert chips |
| `--arm-warning-text` | `#5D3C00` | `#E4B661` | Warning text (calibrated $\ge 5.2:1$ contrast) |
| `--arm-info-bg` | `#F0F6F9` | `#1A252C` | Information panel background |
| `--arm-info-text` | `#3E6E8C` | `#8DB7D2` | Information text ($\ge 5.5:1$ contrast) |

### Plotly Colorway
Unified sequence for all charts, error bands, and categorical series:
```python
COLORWAY = [
    "#3F6B57",  # Sage Green (Primary Series)
    "#3E6E8C",  # Slate Blue (Secondary Series)
    "#B8862B",  # Muted Amber / Ochre
    "#B4483C",  # Terracotta Red
    "#7A6F99",  # Muted Heather Purple
    "#8A8F7C",  # Warm Olive Gray
]
```

---

## 3. Typography & Spacing Scale

### Font Stacks
- **Prose & User Interface**: `system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Monospace (Code, Hashes, Traces)**: `ui-monospace, "Cascadia Mono", Consolas, monospace`
- **Tabular Figures**: `font-variant-numeric: tabular-nums` enforced on all numbers, tables, and KPI metrics to eliminate visual jitter during real-time updates.

### Type Scale
- **Page Title (`h2`)**: `1.65rem` / `700` weight, line-height `1.3`
- **Section Card Header**: `0.95rem` / `700` weight, line-height `1.4`
- **Body Text**: `15px` (`0.95rem`) / `400` weight, line-height `1.5`
- **KPI Value**: `1.75rem` / `700` weight, tabular-nums
- **Captions & Metadata**: `0.78rem` / `400` weight, italicized for source citations

### 8px Spacing Scale
- `4px` (`--arm-space-xs`): Compact badge padding, icon gaps
- `8px` (`--arm-space-sm`): Card padding internal, input element margins
- `12px` (`--arm-space-md`): Standard component gutters
- `16px` (`--arm-space-lg`): Section separation, container gutters
- `24px` (`--arm-space-xl`): Distinct section card spacing
- `32px` (`--arm-space-2xl`): Major page section breaks

### Layout Width
- Max content width: `1280px` centered with auto margins, ensuring balanced reading lines on ultra-wide monitors.

---

## 4. Reusable Component Library (`app/ui/components.py`)

All 17 pages import from `app.ui.components` to guarantee consistent styling:

### `top_bar()`
Renders the top utility bar displaying:
- Product Brand
- Active Baseline Short Hash (`copyable_hash`)
- Active Model and Pipeline Role
- Ollama Online / Offline Chip
- Database Status Chip (`MySQL` / `SQLite`)
- Governance Policy Version
- Last Gate Verdict and Timestamp (cached for 5s via `get_cached_system_status()`).

### `page_header(title, subtitle)`
Renders a sentence-case title and a one-line description establishing the page's functional purpose.

### `kpi_card(label, value, delta=None, help_text=None)`
Renders a KPI card with tabular-numeric value, optional colored delta, and tooltip. Maximum 4 to 5 cards per horizontal row.

### `status_chip(kind, text)`
Dual-encoded status badge combining an icon and a text label:
- `promote` / `fixed`: `:material/check_circle:` + `PROMOTE` / `FIXED`
- `block` / `regressed`: `:material/block:` / `:material/trending_down:` + `BLOCK` / `REGRESSED`
- `warning` / `inconclusive`: `:material/warning:` / `:material/help_outline:` + `WARNING` / `INCONCLUSIVE`
- `info`: `:material/info:` + `INFO`

### `verdict_banner(verdict, summary, p_value=None, delta_pass_rate=None)`
High-prominence banner used for gate decisions (Green for `PROMOTE`, Terracotta for `BLOCK`, Neutral for `INCONCLUSIVE`).

### `section_card(title, subtitle=None)`
Card container header demarcating logical subsections.

### `source_caption(text)`
Italic caption placed directly beneath tables and charts:
```html
<div class="arm-source-caption">Source: Local MySQL database 'scores' table...</div>
```

### `empty_state(message, subtitle=None, icon=":material/inbox:")`
Empty state placeholder with actionable guidance.

### `error_panel(message, how_to_fix=None)`
Clear root-cause error panel with structured resolution instructions.

### Modal Dialogs (`@st.dialog`)
Enforced for all destructive, irreversible, or state-changing actions:
- **Rollback Confirmation**: Mandates written incident justification and specifies the exact inverse Git commit being generated.
- **Baseline Promotion**: Verifies approver identity and checks separation of duties (requester $\ne$ approver).
- **Change Request Rejection**: Requires written rationale before closing request.

---

## 5. Motion, Transitions & Reduced Motion

- **Subtle Transitions**: Hover, focus, and state changes apply `180ms ease-out` transitions on `border-color`, `background-color`, `box-shadow`, and `color`. Layout properties (`width`, `height`, `margin`, `padding`) are strictly forbidden from animating to eliminate flicker.
- **Single Page-Load Fade**: Initial page content renders with a gentle 200ms opacity fade-in. Widget interactions and fragment reruns do not replay this animation.
- **Reduced Motion Support**:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
  ```

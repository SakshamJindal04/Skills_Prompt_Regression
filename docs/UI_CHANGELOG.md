# RegGuard Dashboard UI Refinement Changelog

**Git Branch:** `ui-light`  
**Base Commit:** `c403763` (`ui-refine`)  
**Design Phase:** Light-Only Modern Restyle & High-Clarity Typography

---

## 1. Summary of Changes

| Domain | Before (`ui-refine` & prior) | After (`ui-light`) | User Benefit |
| :--- | :--- | :--- | :--- |
| **Theme Architecture** | Dual light/dark theme switching based on OS media query | **Light-only theme** enforced via `:root { color-scheme: light; }` and `.streamlit/config.toml` (`base = "light"`) | Zero unexpected theme flips; uniform enterprise light appearance on every device. |
| **Page Background** | Off-white canvas `#FAF8F4` / dark `#151A17` | Pristine modern light canvas `#F6F8FB` | Cleaner contrast and reduced visual fatigue. |
| **Card Geometry** | 6px-8px radius with variable shadows | Uniform **12px radius**, 1px border (`#E2E8F0`), soft shadow (`0 1px 2px rgba(15,23,42,0.06)`) | Modern, calm card visual separation with no heavy shadows. |
| **Body Typography** | 15px text with mixed contrast | **16px minimum body text**, line-height 1.55, max 75ch reading width | Substantially improved readability and effortless scanning. |
| **Table Typography** | 13px-14px default cells | **14px minimum table text**, sticky headers (`#F1F5F9`), right-aligned tabular numerals | Zero row jump; numbers align perfectly down columns. |
| **Captions & Provenance** | 11px-12px text, Streamlit 60% opacity attenuation | **13.5px minimum font size**, 100% opacity, color `#475569` (7.58:1 contrast) | Complete legibility for source citations and methodology notes. |
| **Primary Action Buttons** | Saturated green block `#3F6B57` | Modern light fill `#DBEAFE`, border `#93C5FD`, deep navy text `#1E3A8A` | Professional modern feel; distinct visual priority without heavy dark blocks. |
| **Secondary Action Buttons**| Mixed white/gray buttons | Crisp white `#FFFFFF`, border `#CBD5E1`, text `#1E293B`, hover `#F1F5F9` | Clean secondary hierarchy; quiet copy/view buttons. |
| **Status Chips** | Varied badge shapes and saturated borders | Semantic light fill + dark text (e.g., `#DCFCE7`/`#166534`), dual-encoded icon + text | High-contrast status badges complying with WCAG AA. |
| **Sidebar Visuals** | Default Streamlit styling with dark mode vulnerability | Pure white left sidebar (`#FFFFFF`), border `#E2E8F0`, hover `#F1F5F9` | Clean navigation panel seamlessly integrated into light aesthetic. |
| **Plotly Visualization** | Sage/terracotta palette with dark mode toggles | Standardized white plot canvas `#FFFFFF`, grid `#E2E8F0`, marks >= 3:1 contrast | Color-blind safe, print-friendly, crisp chart renderings. |
| **Accessibility Compliance** | WCAG 2.1 AA | **WCAG 2.1 AAA for body text** (14.63:1), WCAG AA for UI, 0 critical / 0 serious violations | Full universal accessibility across all 17 application views. |

---

## 2. Component-by-Component Diff

### `app/ui/styles.css`
- Added `:root { color-scheme: light; }` to suppress OS dark mode overrides globally.
- Removed all `@media (prefers-color-scheme: dark)` styling rules.
- Set base body font size to 16px with line-height 1.55.
- Set table font size to 14px with sticky headers.
- Set caption font size to 13.5px with `#475569` text color and `opacity: 1 !important`.
- Restyled primary action buttons to light tinted blue (`#DBEAFE` fill, `#93C5FD` border, `#1E3A8A` text).
- Restyled secondary action buttons to white with `#CBD5E1` border and `#1E293B` text.
- Standardized card radii to 12px across cards, containers, and verdict banners.
- Added 2px solid `#3B82F6` visible focus rings for interactive elements.

### `app/ui/theme.py`
- Removed dark theme branches from `get_plotly_template()`.
- Standardized plot and paper background to pure white `#FFFFFF`.
- Set axis tick and label colors to `#334155` (10.35:1 contrast against white).
- Calibrated series colorway (`#3B82F6`, `#059669`, `#D97706`, `#EF4444`, `#8B5CF6`, `#64748B`) to guarantee all series marks achieve at least 3.0:1 contrast against white.

### `.streamlit/config.toml`
- Pinned `base = "light"`.
- Configured light tokens: `primaryColor = "#1E3A8A"`, `backgroundColor = "#F6F8FB"`, `secondaryBackgroundColor = "#FFFFFF"`, `textColor = "#1E293B"`.

### `scripts/check_contrast.py`
- Updated evaluation engine to enforce WCAG AAA (>= 7.0:1) for body text, WCAG AA (>= 4.5:1) for secondary text and action buttons, and >= 3.0:1 for chart marks against white.
- Verified 25/25 token pairs passing.

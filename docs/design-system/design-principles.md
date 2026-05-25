# Design Principles & Design System

Arkon uses the **Sahara Design System**, which is built on the principles of **Warm Minimalism**. It leverages soft, organic colors, high-contrast serif typography for headings, and functional geometric sans-serif typefaces for body text to create a clean, professional, yet inviting enterprise user interface.

---

## 🎨 Color Palette & Tokens

The theme configuration is defined in [globals.css](file:///d:/workspace/src/truongnqse05461/arkon/frontend/src/app/globals.css).

### Sahara Warm Palette (Light Theme Default)

| Token | CSS Variable | Hex Value / CSS Value | Description / Usage |
|---|---|---|---|
| **Background** | `--background` | `#faf5ee` | Warm linen background for pages |
| **Foreground** | `--foreground` | `#3a302a` | Deep charcoal/brown for primary readable text |
| **Card** | `--card` | `#f6f0e8` | Off-white warm surface for cards and components |
| **Primary** | `--primary` | `#c2652a` | Burnt sienna used for active elements and primary buttons |
| **Secondary** | `--secondary` | `#ece6dc` | Sand-like grey for secondary tags and panels |
| **Muted Foreground** | `--muted-foreground` | `#78706a` | Softer grey/brown for helper text and subtitles |
| **Destructive** | `--destructive` | `#c0392b` | Red for errors, critical alerts, and destructive actions |
| **Border** | `--border` | `rgba(216, 208, 200, 0.6)` | Light grey-brown for subtle separators and inputs |
| **Ring** | `--ring` | `#c2652a` | Burnt sienna highlight for input focus states |

### Sidebar Custom Tokens

The sidebar has a dedicated color configuration to remain visually separated from page content:
- **Background:** `--sidebar` (`#faf5ee`)
- **Primary:** `--sidebar-primary` (`#c2652a`)
- **Accent:** `--sidebar-accent` (`rgba(194, 101, 42, 0.1)`)
- **Accent Foreground:** `--sidebar-accent-foreground` (`#c2652a`)
- **Border:** `--sidebar-border` (`rgba(216, 208, 200, 0.6)`)
- **Ring:** `--sidebar-ring` (`#c2652a`)

---

## 🔠 Typography

Arkon pairs a serif font for structured titles with a geometric sans-serif font for density and clarity in corporate data tables.

- **Headings (h1, h2, h3, h4):** `"EB Garamond"`, Georgia, serif. This adds a clean, literary, and structured feel to the knowledge wiki.
- **Body & Interface:** `"Manrope"`, system-ui, sans-serif. Manrope provides clean legibility even at small sizes in tabular views.
- **Code & Monospace:** `ui-monospace`, `"Cascadia Code"`, monospace. Used in code editors, markdown renderers, and CLI/API examples.

---

## 🪵 Custom Styling & Utilities

### 1. Iconography (Material Symbols)
Arkon uses **Material Symbols Outlined** for UI icons, configured directly in CSS.
- Default style:
  ```css
  .material-symbols-outlined {
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    line-height: 1;
  }
  ```
- Filled state:
  ```css
  .material-symbols-outlined.filled {
    font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  }
  ```

### 2. Shadows
A custom soft shadow is used for floating elements, popovers, and cards:
- **Shadow Sahara:** `box-shadow: 0 2px 16px rgba(58, 48, 42, 0.04);`

### 3. Notion-Style Scrollbars
For sidebars and narrow scroll-containers, a minimalist scrollbar is defined (`.sidebar-scrollbar`):
- Width: `4px`
- Thumb background: `rgba(0, 0, 0, 0.08)` (transitioning to `rgba(0, 0, 0, 0.14)` on hover)
- Hides automatically when not hovered to avoid visual clutter.

---

## 📐 Layout & Composition Guidelines

1. **Three-Panel Layout for Wiki & Review Console:**
   - **Left Panel (320px wide):** Navigation tree or queues.
   - **Center Panel (flexible width):** Prime content viewer or editor with unified heading hierarchy.
   - **Right Panel (340px wide):** Context, metadata inspector, and actions stack.
2. **Spacing & Padding:**
   - Standard grid margins: `p-6` (`1.5rem`) for container content.
   - Component spacing: `gap-4` (`1rem`) or `gap-6` (`1.5rem`) for vertical stack groupings.
3. **Borders and Cards:**
   - Border radius is standard at `0.625rem` (`10px`).
   - Cards use `--card` background with `--border` lines. Shadows are minimized to maintain flat minimalism.

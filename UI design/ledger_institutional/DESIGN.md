---
name: Ledger Institutional
colors:
  surface: '#f7f9ff'
  surface-dim: '#d5dae2'
  surface-bright: '#f7f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4fc'
  surface-container: '#e9eef6'
  surface-container-high: '#e3e9f0'
  surface-container-highest: '#dde3eb'
  on-surface: '#161c22'
  on-surface-variant: '#44474e'
  inverse-surface: '#2b3137'
  inverse-on-surface: '#ecf1f9'
  outline: '#75777f'
  outline-variant: '#c5c6cf'
  surface-tint: '#4c5e83'
  primary: '#001637'
  on-primary: '#ffffff'
  primary-container: '#172b4d'
  on-primary-container: '#8093bb'
  inverse-primary: '#b4c7f1'
  secondary: '#3f665c'
  on-secondary: '#ffffff'
  secondary-container: '#bee8dc'
  on-secondary-container: '#436a60'
  tertiary: '#241300'
  on-tertiary: '#ffffff'
  tertiary-container: '#402500'
  on-tertiary-container: '#b48b5b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#b4c7f1'
  on-primary-fixed: '#041b3c'
  on-primary-fixed-variant: '#34476a'
  secondary-fixed: '#c1ebdf'
  secondary-fixed-dim: '#a6cfc3'
  on-secondary-fixed: '#00201a'
  on-secondary-fixed-variant: '#274e45'
  tertiary-fixed: '#ffddb9'
  tertiary-fixed-dim: '#edbe8a'
  on-tertiary-fixed: '#2b1700'
  on-tertiary-fixed-variant: '#604017'
  background: '#f7f9ff'
  on-background: '#161c22'
  surface-variant: '#dde3eb'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  title-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  data-cell:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  data-mono:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-xs:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-compact: 0.5rem
  margin: 1.5rem
  margin-panel: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

The design system projects fiduciary rigor, procedural clarity, and institutional authority. Designed specifically for high-stakes financial auditing, receipt reconciliation, and invoice processing, the interface removes visual ornamentation in favor of precision, scannability, and audit-trail integrity.

The personality balances the restrained poise of classical institutional finance with the rapid ergonomic efficiency of modern tooling. The aesthetic avoids consumer fintech tropes—no bright neon accents, no decorative gradients, no translucent frosted glass, and no non-deterministic AI embellishments. Instead, visual hierarchy is governed by strict tabular alignment, muted tactile boundaries, and deliberate information density.

## Colors

The palette establishes an authoritative, document-first canvas designed for extended auditing sessions without visual fatigue.

### Foundations & Surfaces
- **Canvas / Background**: `#F7F7F4` (Warm alabaster/stone ground that softens contrast against raw screens)
- **Surface / Card**: `#FFFFFF` (Pure white for actionable cards, audit sheets, and modal viewports)
- **Surface Muted / Inactive**: `#F0F1EE` (Secondary container fills and disabled inputs)

### Brand & Accents
- **Primary Brand**: `#172B4D` (Deep oceanic navy; drives high-priority CTAs, primary navigation headers, and authoritative checkpoints)
- **Secondary Accent**: `#52796F` (Muted sage/teal; deployed for verified status indicators, reconciliation badges, and balanced balances)

### Structural & Borders
- **Border / Divider**: `#E9ECE8` (Subtle, low-contrast structural dividers)
- **Border Strong**: `#D0D5CE` (Interactive boundaries, input borders on hover/focus)

### Typography Tokens
- **Text Primary**: `#343A40` (Slate charcoal for primary labels, data cells, and headline elements)
- **Text Secondary**: `#6B7280` (Cool neutral gray for metadata, timestamps, and secondary descriptors)
- **Text Inverse**: `#FFFFFF` (For high-contrast badge copy on dark backgrounds)

### Semantic Auditing Tones
- **Success / Matched**: `#287A52` (Background tint: `#EBF5F0`)
- **Error / Discrepancy**: `#B54747` (Background tint: `#FBEAEA`)
- **Warning / Pending Audit**: `#B7791F` (Background tint: `#FEF7EC`)
- **Information / Notice**: `#52677F` (Background tint: `#EFF3F8`)

## Typography

The type hierarchy relies entirely on `Inter`, utilizing native OpenType typographic features to guarantee flawless data alignment across ledgers, currency statements, and reconciliation tables.

### Tabular Formatting Rules
- **Font Feature Settings**: All numerical displays, currency values (`₹ / INR`), receipt IDs, and audit balance sheets must strictly use `font-feature-settings: "tnum" 1, "cv05" 1, "cv11" 1` to guarantee monospaced digit widths and proper character separation.
- **Currency Presentation**: Currency symbols (`₹`) maintain regular font weight alongside bold or semibold values to preserve vertical baseline balance across data tables.
- **Labels & Micro-copy**: Sub-12px elements (`label-xs`) leverage an uppercase transformation with `+0.04em` tracking for receipt status categorizations and audit table column headers.

## Layout & Spacing

The framework uses an exact 8px incremental baseline grid (with 4px micro-increments for compact audit controls). 

### Workspace Shell
- **Viewport Target**: 1440px desktop-first layout strategy, fluidly scaling downward to 1024px while clamping main table content.
- **Fixed Sidebar**: Fixed width of `248px` spanning 100vh, containing administrative navigation, auditor queue counts, and tenant-switching.
- **Auditor Workspace**: Remaining horizontal space functions as a split view when auditing invoices: 55% primary data table / invoice ledger, 45% contextual document inspection viewport.
- **Data Table Density**: Compact table rows default to a height of `36px` to maximize onscreen audit lines; standard rows measure `44px`.

### Responsive Breakpoints
- **Desktop (>= 1440px)**: Persistent 248px navigation sidebar, dual-pane auditing workspace with simultaneous receipt preview pane.
- **Compact Desktop / Tablet Landscape (1024px - 1439px)**: Sidebar shrinks to a persistent 64px icon-only strip; invoice viewer switches to a collapsible side drawer.
- **Tablet Portrait (< 1024px)**: Single column with sheet overlays for detailed receipt verification.

## Elevation & Depth

Depth is established primarily through structural borders (`1px solid #E9ECE8`) and tone contrasts rather than drop shadows. Shadows are deployed sparingly to avoid visual noise during extended review tasks.

- **Level 0 (Base Canvas)**: `#F7F7F4` ground; no elevation, no border.
- **Level 1 (Card & Content Tables)**: `#FFFFFF` surface with a crisp `1px solid #E9ECE8` perimeter. Optional ambient shadow: `0 1px 2px 0 rgba(23, 43, 77, 0.04)`.
- **Level 2 (Popover, Dropdowns, Datepickers)**: Elevated `#FFFFFF` surface bounded by `1px solid #D0D5CE` and supported by an institutional shadow: `0 4px 12px -2px rgba(23, 43, 77, 0.08), 0 2px 4px -1px rgba(23, 43, 77, 0.04)`.
- **Level 3 (Modal & Audit Drawers)**: Floating document canvas overlaid on an authentic translucent shroud (`rgba(23, 43, 77, 0.4)`), styled with `0 12px 24px -4px rgba(23, 43, 77, 0.12), 0 4px 8px -2px rgba(23, 43, 77, 0.06)`.

## Shapes

The shape vocabulary maintains disciplined, restrained geometry that keeps interfaces structural and document-oriented:

- **Primary Cards & Containers**: `8px` (`0.5rem`) corner radius to deliver soft precision without casual circularity.
- **Data Tables & Auditor Sheets**: `8px` corner radius on exterior wrappers; internal row segments retain strict orthogonal geometry (`0px`) with subtle dividers.
- **Controls & Input Fields**: `6px` corner radius for buttons, text fields, filters, and dropdowns.
- **Status Tags & Badges**: `4px` or `6px` radius; pill shapes (`9999px`) are reserved strictly for small numerical notification badges within navigation headers.

## Components

### Buttons
- **Primary**: Background `#172B4D`, label `#FFFFFF`, height `36px`, horizontal padding `14px`, radius `6px`. Hover state: `#1E3A68`. Active: `#11203A`.
- **Secondary**: Surface `#FFFFFF`, border `1px solid #E9ECE8`, label `#343A40`. Hover: `#F7F7F4` background, border `#D0D5CE`.
- **Destructive**: Background `#B54747`, label `#FFFFFF`. Hover: `#9B3B3B`.
- **Ghost**: Transparent background, label `#343A40`. Hover: background `#F0F1EE`.

### Audit Status Chips
- Height `22px`, font size `11px`, weight `600`, radius `4px`, padding `0 6px`.
- **Verified / Matched**: Background `#EBF5F0`, text `#287A52`, border `1px solid #D1EADE`.
- **Discrepancy / Rejected**: Background `#FBEAEA`, text `#B54747`, border `1px solid #F6D0D0`.
- **Audit Required / Pending**: Background `#FEF7EC`, text `#B7791F`, border `1px solid #FDE8C7`.
- **Under Review**: Background `#EFF3F8`, text `#52677F`, border `1px solid #DCE5EE`.

### Data Table (Ledger Grid)
- **Header**: Background `#F7F7F4`, height `32px`, border-bottom `1px solid #E9ECE8`, label style `label-xs` in uppercase, secondary text color `#6B7280`.
- **Rows**: Background `#FFFFFF`, height `38px`, border-bottom `1px solid #E9ECE8`. Alternating zebra striping is disallowed; hover triggers background `#FAFAFA`.
- **Monetary Cells**: Right-aligned, `font-feature-settings: "tnum" 1`, bolded amounts in primary text `#343A40`.

### Form & Filter Inputs
- Height `34px`, border `1px solid #D0D5CE`, background `#FFFFFF`, radius `6px`, padding `0 10px`, font size `13px`.
- **Focus**: Border `1px solid #172B4D` with `0 0 0 1px #172B4D` (crisp ring outline, avoiding blurred glow effects).
- **Invalid**: Border `1px solid #B54747` with `0 0 0 1px #B54747`.

### Checkboxes
- Size `16px × 16px`, radius `4px`, border `1.5px solid #D0D5CE`. Selected state uses fill `#172B4D` with a sharp white checkmark glyph.

### Cards & Content Surfaces
- Pure white background (`#FFFFFF`), `1px solid #E9ECE8`, radius `8px`. Padding follows internal cadence: `16px` for summaries, `24px` for high-level audit metric overviews.
# ServerDash — Design System

## Philosophy

**Sobria · Profesional · Hogar**

ServerDash lives on the operator's screen for hours at a time. The design must be:

- **Sobria (Restrained)**: No decorative noise. Every visual element earns its place. Dark surfaces, deliberate whitespace, quiet defaults.
- **Profesional (Structured)**: Strict hierarchy. Data is instantly scannable. Consistent spacing makes layouts predictable across all views.
- **Hogar (Warmth)**: The orange is the heartbeat — not corporate blue, not cold gray. It signals "this is yours, this is home." Used sparingly so it always means something.

---

## Color Tokens

All colors must use CSS variables. Never hardcode hex values in component styles.

```css
/* Brand */
--brand-orange:       #F97316   /* Primary accent — used sparingly */
--brand-orange-hover: #EA580C   /* Hover/active state of orange */

/* Surfaces (dark-to-light hierarchy) */
--p-surface-ground   /* Page background — darkest */
--p-surface-card     /* Cards, panels, drawers */
--p-surface-900      /* Terminal output, code areas, log panels */
--p-surface-border   /* Dividers, input borders, separators */

/* Text */
--p-text-color        /* Primary text */
--p-text-muted-color  /* Secondary / metadata text */

/* Orange tints (for backgrounds, not text) */
color-mix(in srgb, var(--brand-orange) 8%,  transparent)  /* Subtle bg tint */
color-mix(in srgb, var(--brand-orange) 12%, transparent)  /* Icon ring bg */
color-mix(in srgb, var(--brand-orange) 14%, transparent)  /* Hovered bg */
color-mix(in srgb, var(--brand-orange) 18%, transparent)  /* Focus glow */
color-mix(in srgb, var(--brand-orange) 25%, transparent)  /* Active / accent border */
color-mix(in srgb, var(--brand-orange) 30%, transparent)  /* Icon ring border */
```

---

## Typography

Two fonts, strict roles — never mix them arbitrarily.

| Font | Variable | Role |
|------|----------|------|
| Fira Code | `var(--font-mono)` | Labels, values, metrics, paths, code, counts, panel headers |
| Fira Sans | `var(--font-ui)` | Descriptions, help text, longer prose, tooltips |

### Type Scale

These are the **only** allowed font sizes. No hardcoded `8px`, `9px`, `13px`, `15px`, etc.

```css
--text-2xs:  10px   /* Absolute minimum — section labels, badges, metadata */
--text-xs:   11px   /* Secondary info, muted details */
--text-sm:   12px   /* Standard mono data, table cells, list items */
--text-base: 14px   /* Body text, primary labels */
--text-lg:   16px   /* Section titles, panel headers */
--text-xl:   20px   /* Card values, large metrics */
--text-2xl:  24px   /* Hero numbers (dashboard metrics) */
```

**Updated in `style.css`:** `--text-2xs` must be `10px`, not `8px`. The scale gap between `--text-xs` (11px) and `--text-sm` (12px) is intentionally small — both are readable.

### Typography Rules

- Panel header labels: `font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 2px; text-transform: uppercase;`
- Field labels: `font-family: var(--font-mono); font-size: var(--text-2xs); letter-spacing: 1.5px; text-transform: uppercase;`
- Data values (metrics, counts): `font-family: var(--font-mono); font-size: var(--text-xl) or var(--text-2xl);`
- Table cells: `font-family: var(--font-mono); font-size: var(--text-sm);`
- Descriptions / help text: `font-family: var(--font-ui); font-size: var(--text-sm) or var(--text-base);`
- Error/status text: `font-family: var(--font-mono); font-size: var(--text-xs);`

---

## Spacing Scale

Use multiples of 4px. Never use arbitrary values.

```
4px   — inner padding for tiny elements (badges, chips)
8px   — gap between related items, inner padding for small controls
12px  — standard inner padding, compact panel spacing
16px  — standard gap between sections, form field spacing
20px  — comfortable inner padding for cards
24px  — card/panel padding, section gaps
28px  — generous section spacing
32px  — major section separation
```

---

## Border Radius Scale

```
4px   — badges, small tags, inline chips
6px   — small buttons, table rows, tight controls
7px   — form inputs, input groups
8px   — standard buttons, medium cards
12px  — panel sections, expanded content areas
14px  — main login/modal cards
```

---

## Surface & Card Patterns

### 1. Main Card (full view card, login-style)

Used for: login page, modal dialogs, settings panels.

```css
background: var(--p-surface-card);
border: 1px solid var(--p-surface-border);
border-radius: 14px;
box-shadow:
  0 0 0 1px color-mix(in srgb, var(--brand-orange) 12%, transparent),
  0 20px 60px -12px rgba(0, 0, 0, 0.5);
/* Orange top accent bar */
padding-top: 3px;
background-image: linear-gradient(
  to bottom,
  var(--brand-orange) 0px,
  var(--brand-orange) 3px,
  var(--p-surface-card) 3px
);
```

### 2. Panel Card (splitter panels inside views)

Used for: left/right panels in Scripts, Files, Crontab, Services, Logs views.

```css
background: var(--p-surface-card);
border-right: 1px solid var(--p-surface-border);  /* or border-left for right panel */
/* NO top accent bar — panels are nested, not top-level */
```

### 3. Terminal / Output Area

Used for: log output, script output, command results.

```css
background: var(--p-surface-900);
border-radius: 8px;
font-family: var(--font-mono);
font-size: var(--text-sm);
```

### 4. Stat Card (metrics, counters)

Used for: dashboard metric cards, log stats row.

```css
background: var(--p-surface-card);
border: 1px solid var(--p-surface-border);
border-radius: 10px;
border-left: 3px solid <accent-color>;  /* color varies by metric type */
padding: 16px 20px;
```

---

## Panel Header Pattern

Every list/data panel must have a header bar. Use this pattern exactly.

```html
<div class="panel-header">
  <i class="pi pi-[icon] header-icon" />       <!-- orange, 12px -->
  <span class="header-label">SECTION NAME</span>  <!-- mono 2xs, uppercase, muted, flex:1 -->
  <span class="header-count">{{ n }}</span>    <!-- orange pill badge -->
  <!-- optional action buttons: text+rounded+small -->
</div>
```

```css
.panel-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 12px 9px;
  border-bottom: 1px solid var(--p-surface-border);
  flex-shrink: 0;
}
.header-icon {
  font-size: 12px;
  color: var(--brand-orange);
}
.header-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);   /* 10px */
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  flex: 1;
}
.header-count {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);   /* 10px */
  font-weight: 600;
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.6;
}
```

---

## Terminal Header Pattern

Used above log/output panels to show the source script/service context.

```html
<div class="terminal-header">
  <i class="pi pi-[icon]" style="color: var(--brand-orange)" />
  <span class="terminal-title">script-name.sh</span>  <!-- mono sm, brand-orange -->
  <span class="terminal-source">output</span>          <!-- mono 2xs, muted -->
  <!-- spacer -->
  <Tag :value="exitCodeLabel" :severity="severity" rounded />
</div>
```

```css
.terminal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--p-surface-900);
  border-bottom: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
}
.terminal-title {
  font-family: var(--font-mono);
  font-size: var(--text-sm);   /* 12px */
  color: var(--brand-orange);
  font-weight: 600;
}
.terminal-source {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);   /* 10px */
  color: var(--p-text-muted-color);
  margin-left: auto;
}
```

---

## Icon Ring Pattern

Used when a single icon needs visual weight (brand headers, empty states with context).

```html
<div class="icon-ring">
  <i class="pi pi-[icon]" />
</div>
```

```css
.icon-ring {
  width: 40px;    /* or 52px for larger contexts */
  height: 40px;
  border-radius: 10px;   /* or 14px for large */
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 30%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon-ring .pi {
  font-size: 18px;   /* or 22px for large */
  color: var(--brand-orange);
}
```

---

## Empty State Pattern

Used when a list/panel has no data. Always centered in the container.

```html
<div class="empty-state">
  <i class="pi pi-[icon] empty-icon" />
  <span class="empty-text">Descriptive message here.</span>
</div>
```

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 16px;
  color: var(--p-text-muted-color);
}
.empty-icon {
  font-size: 28px;   /* ALWAYS 28px, never larger or smaller */
  opacity: 0.4;
}
.empty-text {
  font-family: var(--font-mono);
  font-size: var(--text-sm);   /* 12px */
  text-align: center;
}
```

---

## Badge / Count Pills

Inline count or status pill attached to items.

```css
/* Orange count (panel headers, cron badges) */
.badge-orange {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  font-weight: 600;
  color: var(--brand-orange);
  background: color-mix(in srgb, var(--brand-orange) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-orange) 25%, transparent);
  border-radius: 4px;
  padding: 1px 6px;
  line-height: 1.6;
}
/* Neutral count */
.badge-neutral {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--p-text-muted-color);
  background: var(--p-surface-ground);
  border: 1px solid var(--p-surface-border);
  border-radius: 4px;
  padding: 1px 6px;
}
```

---

## Form Inputs

All form fields must have **visible labels above the input** — never placeholder-only.

```html
<div class="field">
  <label for="field-id" class="field-label">LABEL TEXT</label>
  <InputText id="field-id" ... />
</div>
```

```css
.field { display: flex; flex-direction: column; gap: 6px; }

.field-label {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);   /* 10px */
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}

/* Input focus: orange border + soft glow */
:deep(.p-inputtext:focus) {
  border-color: var(--brand-orange);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand-orange) 18%, transparent);
}
```

---

## Interactive States

### Buttons

- **Primary action** (CTA, submit): full `--brand-orange` background, mono font, 12px, letter-spacing 1.5px, height 40–44px, border-radius 8px
- **Secondary action** (icon buttons in headers): `text + rounded + size="small"`, color `var(--p-text-muted-color)`, hover color `var(--brand-orange)`
- **Danger action**: PrimeVue severity="danger", separated visually from primary

### Hover / Active Pattern (for custom buttons and list items)

```css
.item:hover {
  background: color-mix(in srgb, var(--brand-orange) 8%, transparent);
}
.item.active, .item:focus-visible {
  background: color-mix(in srgb, var(--brand-orange) 14%, transparent);
  outline: none;
}
```

### Transition

All interactive elements: `transition: background 0.15s, color 0.15s, border-color 0.15s, box-shadow 0.15s`

---

## Error / Status Banners

```css
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 7px;
  background: color-mix(in srgb, #ef4444 12%, transparent);
  border: 1px solid color-mix(in srgb, #ef4444 30%, transparent);
  font-family: var(--font-mono);
  font-size: var(--text-xs);   /* 11px */
  color: #f87171;
}
/* Warning */
.warn-banner { ...same but with #f59e0b... }
/* Success */
.success-banner { ...same but with #22c55e... }
```

---

## Animation Guidelines

- **Entry animations**: `opacity 0 → 1` + `translateY(8–12px) → 0`, duration 200–300ms, `ease-out`
- **Micro-interactions** (hover, toggle): 150ms max
- **Always include**: `@media (prefers-reduced-motion: reduce) { animation: none; transition: none; }`
- Never animate `width`, `height`, or `font-size` — use `transform` and `opacity` only

---

## Layout Structure (per view)

Every view with a splitter follows this structure:

```
<div class="[view-name]-view">          <!-- full height, flex column -->
  <Splitter class="[view]-splitter">    <!-- flex: 1, min-height: 0 -->

    <SplitterPanel :size="25-30">       <!-- Left: list panel -->
      <div class="list-panel">          <!-- flex column, full height -->
        <div class="panel-header">...</div>   <!-- sticky header -->
        <div class="panel-scroll">            <!-- flex: 1, overflow-y: auto -->
          <!-- content -->
        </div>
      </div>
    </SplitterPanel>

    <SplitterPanel :size="70-75">       <!-- Right: detail panel -->
      <!-- content or empty state -->
    </SplitterPanel>

  </Splitter>
</div>
```

```css
.[view]-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
}
.[view]-splitter {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
}
.list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--p-surface-card);
  border-right: 1px solid var(--p-surface-border);
  overflow: hidden;
}
.panel-scroll {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
```

---

## Sidebar & Header

These are already well-styled. **Do not modify** unless fixing a specific bug.

---

## Anti-Patterns (Never Do)

| Avoid | Use Instead |
|-------|-------------|
| `font-size: 8px` or `9px` | Minimum `var(--text-2xs)` = 10px |
| Hardcoded hex colors | `var(--brand-orange)` or `color-mix(...)` |
| Placeholder-only form labels | Always visible `<label>` above input |
| `font-size: 13px`, `15px`, etc. | Only use tokens from the type scale |
| Different empty state styles per view | Always use the `.empty-state` pattern |
| Orange used as background color | Orange is for icons, borders, accents, text highlights — never as a fill background |
| All-caps with no letter-spacing | Always pair `text-transform: uppercase` with `letter-spacing: 1.5px` minimum |
| PrimeVue `<Card>` for stats | Use `.stat-card` with colored left border |
| `FloatLabel` for important form fields | Use visible labels — FloatLabel hides label until focus |

---

## Quick Reference: Orange Usage Hierarchy

| Context | Orange Usage |
|---------|-------------|
| Panel header icon | `color: var(--brand-orange)` — always |
| Active nav item | Icon + text in `var(--brand-orange)` |
| Interactive count badge | Orange tint bg + orange text |
| Focused input | Border + box-shadow glow |
| Top accent bar (main cards) | 3px top border gradient |
| CTA button | Full orange bg |
| Star / favorite icon | Orange fill when active |
| Running indicator | Orange animated pulse strip |
| Hover bg tint | `color-mix(in srgb, var(--brand-orange) 8%, transparent)` |
| Decorative background | `color-mix(in srgb, var(--brand-orange) 5–8%, transparent)` max |

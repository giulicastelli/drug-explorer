# Design system

The look of the page, written down so that a change has one place to start. One dark theme, one data palette, one rule for colour. Why these choices and not others: D-57 to D-59 in `docs/decision_log.md`. Written on 6 Nov 2026, the day the interface was redesigned and the atlas was added.

## The rules

1. **Colour follows the kind of the ingredient, never its rank.** Blue = its labels are Rx only, orange = OTC only, aqua = both. A bigger dot or a longer bar is never a different colour.
2. **Dimmed = no match.** When a search is on, the dots whose labels do not mention the condition turn grey (`#75746e`, 3.7:1 on the chart surface, full opacity) and keep a small fixed size, while the matching dots grow with the number of their labels that mention the condition. They stay on the map, so the shape of the map stays.
3. **Ring = the open ingredient.** One light ring (ink `#f0efec`, 2 px, on a 5 px dark halo, drawn above the region names) marks the ingredient shown in the side panel. Colour is not used for this, so the ring never reads as a kind.
4. **The legend is always present.** The kind legend and the size legend sit above the map, with or without a search. A kind that has no dot on the map gets no entry.
5. **Amber is a highlight, not data.** It is used only behind the matched word in a label text (`rgba(201,133,0,.32)`).
6. **Violet is for controls only.** The accent (`#9085e9`) marks the selected tab, pill and focus. It is never a data colour, so it cannot be read as Rx or OTC.
7. **Near means "described with similar words".** The page says so under the map and in the About tab. The axes have no unit.

## Tokens

### Colour (dark mode)

| Token | Value | Used for |
|---|---|---|
| page plane | `#0d0d0d` | page background, halo around dots and region names |
| chart surface | `#1a1a19` | cards, map and bar charts, metric tiles, chips |
| ink | `#f0efec` | titles, the answer sentence, the focus ring |
| ink 2 | `#c3c2b7` | body text, legends, region names |
| muted | `#898781` | eyebrow, notes, "other" kind |
| gridline | `#2c2c2a` | borders of cards and chips, bar-chart grid |
| data 1, blue | `#3987e5` | Rx only |
| data 2, orange | `#d95926` | OTC only |
| data 3, aqua | `#199e70` | Rx and OTC |
| dimmed | `#75746e` | a dot that does not match the search (3.7:1 on the surface: WCAG 1.4.11 asks 3:1 for a mark you can click) |
| accent, violet | `#9085e9` | primary colour and link colour of the theme (palette slot 7) |
| highlight | `rgba(201,133,0,.32)` | the matched word in a label card |

### Type

| Role | Font | Where |
|---|---|---|
| Text | Fira Sans, 400-700 | everything |
| Numbers and code | Fira Code, 400-500 | the eyebrow, `.de-num`, code |

Sizes: title 2 rem, answer sentence 1.15 rem, subtitle .95 rem, card text .9 rem, chips and notes .8 rem, region names on the map 11 px.

### Spacing and radius

Base radius 6 px (`baseRadius`), the same for cards, tiles and inputs. Chips are fully round (999 px). Card padding .7 rem by .85 rem, space between cards .55 rem. The map is 720 px high; on the page it takes 13 of 20 columns, the side panel 7.

## Components

| Component | What it is | Notes |
|---|---|---|
| Header | eyebrow, title, one line of subtitle | the subtitle shows the label count and the export date, and says "Not medical advice" |
| Search | text input and a segmented control (All, Rx, OTC; the long names are in its help) | the control filters the counts and the map |
| Pills | six example conditions | a pill copies its word into the search box |
| Answer sentence | one sentence with the counts | ingredients, labels, Rx, OTC, the top three |
| Tabs | Atlas, Top ingredients, About the data | the map comes first |
| Map | the atlas: one dot per ingredient | dot colour = kind; dot size = labels (or labels that match, during a search); region names (their first two words) in a plane-colour halo, left- or right-aligned near the edges so none is cut; click a dot to open it; scroll to zoom |
| Metric tiles | Labels, Mention "condition" | two tiles with a border |
| Chips | kind, region, class | the kind chip repeats the dot colour |
| Neighbours table | the 12 most similar ingredients, with a similarity bar 0 to 1 and a Match tick | pick a row to open that ingredient (keyboard: Shift+Space on the row) |
| Label card | brand, maker, date, type, the text around the match | match behind amber; text is escaped before the highlight is added |
| Bar chart, table | the ranking tab | same kind colours: Rx blue, OTC orange, other muted |

## Where each token lives in code

- **`app/.streamlit/config.toml`**: the theme (base dark, plane, surface, ink, border, accent, radius), the two fonts and the chart colour list. This file is copied into the app image.
- **`app/dashboard.py`**: the constants for the kind colours, the bar colours, ink, muted, surface, plane, gridline and dimmed; and one CSS block with the classes `de-eyebrow`, `de-title` (the page's one `h1`), `de-h` (the `h3` section titles), `de-sub`, `de-answer`, `de-chip`, `de-dot`, `de-card`, `de-num`, `de-note` and `de-sr` (text for screen readers only). The map layers (dots, ring, region names) are built with altair in the same file.
- **`sql/queries.sql`**: no colour. It only gives the page the kind of each ingredient through its Rx and OTC counts.
- If a value is in both the config file and the Python constants, change both. The page's own CSS and chart code use the Python constants, not the theme file, so the two are kept equal by hand (Judgement: a small duplication that is cheaper than a helper).

## Sources and what was checked

- **Method and checklist:** a "data-dense dashboard" style guide. Its recommendation for this app: style "Data-Dense Dashboard", dark mode supported, Fira Sans for text and Fira Code for numbers, blue for data with amber for highlights. Its checklist: contrast 4.5:1, visible focus, reduced motion, no emoji as icons, hover states.
- **Colours:** a validated data-visualisation palette, dark mode. Checked with a contrast validator, `--pairs all --mode dark`: every check passes; the worst colour-blind distance (delta E) is 9.4, the worst for normal vision 20.9, and all three data colours reach 3:1 against the chart surface.
- **Idea:** XO by XLN Audio, a map of drum samples in which similar sounds sit close. Here, close means described with similar words (method: D-53 to D-56).
- **Reviews (6 Nov, three checks on the running page, summarised here):**
  - *Design critique* (layout and readability): 11 findings. Fixed: region names colliding (two words, edge alignment, bigger halo, ring drawn last), matching dots too small and grey too faint (sizes 60-560, grey raised), clipped table columns (shorter headers, "–" for no class, a narrower neighbours table), the map shorter than the side panel (620 to 720 px), long filter names clipped on a phone (All / Rx / OTC), legend entries for types with no data, the empty "Class" chip, small tabs, rounded ends in the middle of stacked bars. Not done: hiding region names on narrow screens (Streamlit cannot tell the chart its width).
  - *Accessibility audit* (WCAG 2.1 AA, contrast measured with the WCAG formula): text tokens all pass (ink 15.2:1, ink 2 9.7:1, muted 4.85:1, violet 5.6:1 on the surface; the highlighted word 9.1:1). Fixed: grey dots 2.1:1 to 3.7:1; the chart now has a description (its accessible name); a hidden live status says which ingredient the panel shows; real `h1` and `h3` headings; the keyboard route (the box above the panel, Shift+Space on a table row) is written on the page. Not fixable here: Streamlit's data tables are drawn on a canvas, so screen readers get little from them; the selectbox is the accessible route. Not done: a second shape per kind on the map (the chip, tooltip and legend give the kind in words).
  - *Interaction test*: see the decision log, D-57.

## What is not done

- **No light mode.** The page is dark only. The palette has a light mode, but it was not validated for this page.
- **The fonts need internet.** They load from Google Fonts. Offline, the browser uses its own sans-serif, and the page still works but looks different.
- **Reduced motion and hover states** come from Streamlit's own components. The page adds no animation of its own, and no check of these two items has been made yet (Judgement).
- **Some region names are odd** (for example "inhibitor, cell, women"). They are chosen by a program, not by a person (D-55).
- **On the map, kind is shown by colour only.** The legend, the tooltip and the panel's chip say it in words; no second shape per kind was added (the three colours pass the colour-blind check).

# Design system and frontend mapping
Source: original templates document/cover/picks/grid/week/feature.html.j2, workbook Lists. Magazine canvas 1080×1350; not a responsive application specification. Brand yellow #FFD400, ink #0E0E0E, cream #F4F1EA, red #E4002B as proposed brand tokens; source category colors seeded exactly. Typography Anton (display), Archivo (body), JetBrains Mono (metadata); admin prioritizes legibility and system fallbacks. Original font binaries not distributed in this package.

| Publication sample | Admin source | Future frontend |
|---|---|---|
| Cover | issue metadata, cover and lines, photo, accent | issue landing/hero |
| Picks | issue editorial intro, byline/headshot, ordered picks, event details | curated list and event links |
| Grid | editorial day, eligible occurrence schedules, category colours, spans | responsive timeline/list |
| Full week | eligible occurrences and prices, category, venue, disclosures | date/category filters and detail |
| Feature | feature title/subtitle/kicker, tips, sponsor, teasers | feature article and upcoming events |
| Shared document | publication labels, typography, theme, mock label | shared design tokens and footer |

Admin navigation: dark sidebar, yellow selected state with text/icon not color alone, light neutral work surface; visible focus; accessible forms, table captions, labels and error feedback. 360px mobile navigation collapses; large lists use pagination, responsive card mode; not fixed magazine dimensions. Future frontend must not be implemented now. Visual acceptance: compare original rendered sample with approved snapshots before renderer changes; no separate public web code was present in archive.

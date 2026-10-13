# Board: SOC Monitor (phases from CLAUDE.md brief)

Branch: `build/phases-2-7` (main untouched). One commit per phase.

## Done (awaiting Sahith's review)
- Phase 2: framing (character + bit stuffing), CRC-12/16/CCITT, frame format, experiment CSVs
- Phase 3: sensors, routers, collector, Stop-and-Wait ARQ over UDP/TCP
- Phase 4: detector (5 rules + flooding + firewall-block alert), ACL firewall, token bucket
- Security fix: detector uses receive time (not forgeable event ts); token bucket fails closed
- Phase 5: dashboard (Overview, Topology, Controls, Packet Inspector), light/dark mode
- Phase 6: FTP reports, SMTP alert emails, whitelisted diagnostics (+ 3 dashboard tabs)
- Phase 7: README, SYLLABUS_MAP.md, screenshots, two-PC node selection, clean Ctrl+C/SIGTERM

## In Review
- Dashboard rebuilt with React + shadcn/ui on branch `ui/shadcn` (from `ui/polish`), restyled after shadcndesign `dashboard-1`, light mode only. All 7 tabs keep their content and behaviour; API unchanged apart from a new `GET /api/meta`. Python 158/158, Vitest 23/23, tsc + eslint + build clean, all 7 demo steps clicked through in Playwright (1440px and 390px).
- Review fixes (follow-up to d9cd27f, not yet committed): tabs stay mounted so terminal output, inspector selection and filters survive tab switches, and only the shown tab polls; polling survives StrictMode and pauses while hidden; concurrent actions track their own pending state; slider value held until the status poll catches up; alerts that arrive while Overview is hidden fade in when it is shown. Python 158/158, Vitest 32/32, tsc + eslint + build clean. Checked in Playwright: a brute force launched from Controls fades in on Overview while older alerts don't; console clean.

## Blocked
- none

## To review
- Added a "Start malware beacon" control and a LOW "Firewall block" alert (not literally in the brief; needed to demo the C2 rule and to make blocks visible).
- Helper modules beyond the brief's folder list: datalink/frame.py, network/transport.py, network/node.py, soc/state.py, soc/system.py, dashboard/inspector.py, datalink/experiment.py.
- Two-PC mode: dashboard changes only affect the SOC PC's nodes; sensor retransmit/lost counters stay on the sensor PC.
- lab_code/ had no source files, so framing/CRC/Dijkstra are textbook-style.
- Deleted with Sahith's OK: old vanilla UI (`dashboard/templates/index.html`, `static/style.css`, `static/app.js`), IBM Plex fonts in `static/fonts/`, `docs/screenshots/emails-dark.png`, `diagnostics-dark.png`. Geist's OFL licences ship in `static/dist/fonts/`.
- `@shadcndesign/dashboard-1` is a paid Pro block (not in the free registry), so it was not installed; the look was recreated from its public preview.
- Brief items overridden by Sahith's "look like dashboard-1, light mode only": no dark mode, Geist instead of IBM Plex, black primary instead of blue, tinted severity pills.
- Edited shadcn sources on purpose: toggle "on" = solid primary, severity Badge variants, roomier table cells, sheet overlay has no backdrop blur, use-mobile uses useSyncExternalStore (lint fix).

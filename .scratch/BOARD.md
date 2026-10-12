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

## Blocked
- none

## To review
- Added a "Start malware beacon" control and a LOW "Firewall block" alert (not literally in the brief; needed to demo the C2 rule and to make blocks visible).
- Helper modules beyond the brief's folder list: datalink/frame.py, network/transport.py, network/node.py, soc/state.py, soc/system.py, dashboard/inspector.py, datalink/experiment.py.
- Two-PC mode: dashboard changes only affect the SOC PC's nodes; sensor retransmit/lost counters stay on the sensor PC.
- lab_code/ had no source files, so framing/CRC/Dijkstra are textbook-style.

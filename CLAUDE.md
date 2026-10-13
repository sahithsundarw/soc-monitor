# Project notes

## Commands (PowerShell, run from soc-monitor/)
- Create env: `uv venv` then `.venv\Scripts\activate` (Linux: `source .venv/bin/activate`)
- Install: `uv pip install -r requirements.txt`
- Tests: `python -m unittest discover -s tests -v` (~1 min; network tests use real sockets on ports shifted by +30000..33000, see `tests/helpers.py`)
- Everything (nodes, FTP, SMTP, dashboard): `python run_demo.py [--noise 0.1] [--verbose]` → http://127.0.0.1:5000; Ctrl+C stops cleanly
- Experiment CSVs: `python -m datalink.experiment` → `results/`
- Format: `uvx black .` and `uvx isort --profile black .` (dev tools only, not dependencies)
- Run modules as packages from the project root (`python -m network.routing`), never `python network/routing.py`.
- Dashboard (from `dashboard/web/`, Node 22+): `npm run dev` (:5173, proxies /api to :5000), `npm test` (Vitest), `npx eslint .`, `npm run build` (tsc + Vite → `dashboard/static/dist/`, committed so lab PCs need no Node). Rebuild and commit dist after every frontend change; `tests/test_dashboard.py` checks the build.

## Frontend (Sahith lifted brief rule 3 and "Plain HTML/CSS/JS only" on 2026-10-13)
- React 19 + Vite + Tailwind v4 + shadcn/ui (radix base, lucide icons) in `dashboard/web/`. Still offline: everything, including the Geist fonts (fontsource), is bundled.
- Look follows shadcndesign's `dashboard-1` (Pro, not installed; recreated with free shadcn parts): light mode only, white page, breadcrumb top bar, big page title + actions (`components/page.tsx`), stat strip with dividers, sections instead of cards, tables in bordered panels, black primary.
- Kept from the brief: severity colours only on alerts (Badge variants `critical|high|medium|low`), ≥14px text, mono for addresses/hex/timestamps. Palette tokens live in `src/index.css`.
- Flask serves `static/dist/index.html` at `/`; fixed lists come from `GET /api/meta`. Every tab stays mounted (hidden with `hidden`, so state survives tab switches), but a tab polls its endpoints only while it is shown (`usePoll(..., { enabled: active })`).

## Config
- `config_loader.load_config()` is the single way to read `config.json`.
- Each node has `host_ip` (real bind address, 127.0.0.1 on one PC) and `sim_ip` (the logical IPv4 shown in frames and on the dashboard). Moving to two lab PCs means editing `host_ip` only: `SocSystem` starts only nodes whose `host_ip` is local, and services/dashboard only on the SOC's PC.

## Structure notes (beyond the brief's folder list)
- `datalink/frame.py` frame format + live `LinkSettings`; `network/transport.py` UDP/TCP servers (one frame per datagram / per TCP connection); `network/node.py` forwarding-table cache + noisy `transmit`; `soc/state.py` shared counters; `soc/system.py` wiring; `dashboard/inspector.py` layer breakdown.
- Collector pipeline order: unframe → CRC (NAK only known sensors) → firewall → token bucket → ACK → dedup → detector. Blocked/policed frames are never ACKed.
- Detector windows use receive time, never the event's `ts` (forgeable). Token bucket fails closed for unknown senders.
- API JSON shape is always `{"data": ..., "error": null | "message"}`.

## Lab code
`lab_code/` contains no source files, only `README.md` with the lab syllabus. Per hard rule 5, framing.py, crc.py and routing.py use simple textbook-style implementations; flag this to Sahith when writing them.

| Lab week | Topic | Used in |
|---|---|---|
| Week 9 | Framing: character, character stuffing, bit stuffing | datalink/framing.py |
| Week 10 | CRC-12, CRC-16, CRC-CCITT | datalink/crc.py |
| Week 11 | Basic networking commands | services/diagnostics.py |
| Week 12 | Establishing a network between computers | soc/sensor.py, network/router.py, soc/collector.py, datalink/arq.py |
| Week 13 | Configuring an FTP server | services/ftp_archive.py |
| Week 14 | Dijkstra shortest path | network/routing.py |

---

# PROJECT BRIEF: SOC Telemetry Monitor with Secure Framing and Auto-Rerouting

You are helping me (a student) build my Computer Networks course project. Save this brief as CLAUDE.md in the project root first, then follow it in every session.

## What the project is
A small Security Operations Center (SOC) system. Simulated sensors (firewall, IDS, auth server) generate security events and send them through a simulated router network to a central SOC collector. The collector verifies frame integrity with CRC, requests retransmission of corrupted frames, detects attacks, filters traffic with a firewall, emails critical alerts, archives reports via FTP, and shows everything on a live, clean, professional web dashboard.

## Hard rules
1. Python 3.10+. Third-party packages ONLY: flask, pyftpdlib, aiosmtpd. Everything else from the standard library (socket, threading, subprocess, ftplib, smtplib, json, random, time, ipaddress, logging, unittest). List them in requirements.txt.
2. Must run on Windows AND Linux lab PCs. Detect the OS for commands (ping -n vs -c, tracert vs traceroute, ipconfig vs ifconfig). Use pathlib.
3. Must work OFFLINE. No CDN links or external libraries in the frontend. Draw the topology and charts with plain JavaScript + inline SVG/canvas.
4. All IPs, ports, node names, link costs, CRC type, framing method, firewall rules and token bucket settings live in config.json, so I can run on one PC (127.0.0.1, different ports) or across two lab PCs by editing one file.
5. My lab code is in ./lab_code/. Before writing framing.py, crc.py or routing.py, READ my lab files and reuse my logic and naming style, refactored into clean functions. If a file is missing, write simple textbook-style code and tell me.
6. Code must be readable by a student: short functions, docstrings naming the networking concept shown (e.g. "Bit stuffing, Forouzan Ch. 11"), comments on tricky parts, no clever one-liners.
7. Every module gets unittest tests in tests/ and an `if __name__ == "__main__":` console demo where it makes sense.
8. Work ONE PHASE AT A TIME. At the end of each phase: run the tests, tell me how to run the demo, briefly explain what you built, then STOP and wait for me.
9. No network calls outside localhost / the IPs in config.json.
10. Keep scope tight. Do not add features or protocols that are not in this brief.

## Design and quality standard
This project must look and feel clean and professional, like a real product, not a student demo.

Frontend:
- Minimal "operations console" design: spacing 4/8/16/24/32 only, 8px radius everywhere, panels separated by 1px lines (no drop shadows; only the toast and chart tooltip float), no clutter.
- IBM Plex Sans (400/600) for the UI and IBM Plex Mono for addresses, frames, hex/binary and logs, self-hosted as woff2 in static/fonts (OFL, works offline).
- Restrained palette: neutral greys for layout, one accent colour (blue) for interaction, selection, the active route and the main chart series, and severity colours used ONLY for alerts, as text (CRITICAL red, HIGH orange, MEDIUM amber, LOW steel blue). Every text colour >= 4.5:1. Light and dark mode with a toggle, built on CSS variables.
- Layout: full-width top bar with the project name, page title, system status (running/stopped) and live counters; fixed left sidebar for navigation; content in a grid of bordered panels.
- Each panel has a short title and its content, nothing extra (no captions, taglines, icons or eyebrow labels). Key numbers in one stat strip. Tables with zebra rows and clear headers. Encode each fact once.
- Subtle interaction only: hover states on buttons, a short fade when new alerts arrive, a gentle pulse on the active route in the topology. No flashy effects.
- Empty and loading states for every panel (e.g. "No alerts yet").
- Readable on a classroom projector: minimum 14px body text, good contrast.
- Plain HTML/CSS/JS only: templates/index.html, static/style.css, static/app.js.

Code and repo:
- Consistent naming, type hints on all functions, docstrings on every module and public function.
- No dead code, no commented-out blocks, no debug prints; use the logging module with a clear format.
- Black-style formatting (88 chars) and sorted imports.
- Every module starts with a short header comment: what it does and which networking concept it demonstrates.
- Clean console output from run_demo.py: a short startup banner, then one aligned line per service showing its name, address and port.

## Folder structure
soc-monitor/
  CLAUDE.md, README.md, requirements.txt, config.json, run_demo.py
  lab_code/        (my original lab files, read-only)
  datalink/        framing.py, crc.py, arq.py
  network/         topology.py, routing.py, router.py
  soc/             events.py, sensor.py, collector.py, detector.py, firewall.py, qos.py
  services/        ftp_archive.py, mailer.py, diagnostics.py
  dashboard/       app.py, templates/index.html, static/style.css, static/app.js
  reports/, logs/, ftp_root/, results/
  tests/

## Frame format
FLAG | HEADER | PAYLOAD | CRC | FLAG
HEADER: src_id, dst_id, src_ip, dst_ip, seq_no (0/1 for Stop-and-Wait), frame_type (DATA/ACK/NAK), ttl, priority (0 normal, 1 high, 2 critical).
PAYLOAD: event JSON, e.g. {"ts":..., "sensor":"fw01", "type":"failed_login", "src_ip":"192.168.1.55", "user":"root", "dst_port":22}.
CRC is computed over HEADER+PAYLOAD before stuffing. Stuffing applies to everything between the flags. Receiver: find flags → destuff → split → verify CRC → parse. Framing method (character/bit) and CRC type (CRC-12/CRC-16/CRC-CCITT) are set in config.json and switchable from the dashboard.

## PHASES

### Phase 0 – Setup
Create the folder structure, config.json with defaults (S1 firewall, S2 IDS, S3 auth server, R1–R4 routers, SOC; each with an IPv4 address and port; weighted links), requirements.txt, a minimal Flask app showing "SOC Monitor" at localhost:5000, and CLAUDE.md. Read lab_code/ and list what you found.

### Phase 1 – Topology and Dijkstra (Lab Week 14)
topology.py: weighted undirected graph loaded from config; fail_link(a,b), restore_link(a,b), set_cost(a,b,c).
routing.py: Dijkstra (from my Week 14 code) returning path + cost; build_forwarding_table(node) giving the next hop for each destination.
Console demo: print the route S1→SOC and each router's forwarding table, fail a link, print the new route and updated tables.

### Phase 2 – Framing and CRC (Labs Week 9 & 10)
framing.py: character stuffing (FLAG/ESC bytes) and bit stuffing (01111110 flag, insert 0 after five consecutive 1s), each with stuff and destuff; a function reporting stuffing overhead %.
crc.py: CRC-12 (x^12+x^11+x^3+x^2+x+1), CRC-16 (x^16+x^15+x^2+1), CRC-CCITT (x^16+x^12+x^5+1) via binary polynomial division on bit strings, matching my lab approach; inject_errors(bits, n) to flip random bits.
Tests: round-trip framing for both methods; a corrupted frame must fail CRC.
Experiment script: 1000 random frames with injected errors → detection rate for each CRC, and character vs bit stuffing overhead, saved as CSV in results/.

### Phase 3 – Sensors, routers, collector, ARQ (Lab Week 12)
events.py: generators for normal traffic, failed SSH logins, port scans and malware beacons, with an attack mode for bursts.
sensor.py: build event → frame → send to its first-hop router. Routine events over UDP, HIGH/CRITICAL events over TCP. Each sensor runs on its own port from config.
router.py: forwarder threads that receive a frame, decrement TTL, look up the next hop in the forwarding table from Phase 1, log the hop and forward it. When a link fails, tables are rebuilt and traffic follows the new path.
collector.py: TCP and UDP servers on the SOC. Destuff → verify CRC → parse. On CRC failure, log an integrity alert and send a NAK.
arq.py: Stop-and-Wait ARQ for sensor ↔ collector: sequence number 0/1, ACK on good frame, NAK on bad frame, timeout and retransmit, with a max retry limit. Log every send/ACK/NAK/timeout/retransmit.
The collector keeps thread-safe shared state for the dashboard: per-sensor counts of good, corrupted, retransmitted and lost frames, split by UDP/TCP, plus the current route.
Demo: run_demo.py starts collector, routers and 3 sensors; events flow, the route is printed, and injected errors trigger NAKs and retransmissions.

### Phase 4 – Detection, firewall, token bucket
detector.py: rules with severity (LOW/MEDIUM/HIGH/CRITICAL):
- 5+ failed logins from one IP within 60 s → brute force
- 10+ distinct ports from one IP within 5 s → port scan
- event from an IP not listed in config → unknown host
- beacons at a regular interval to the same destination → malware C2
- many CRC failures on frames arriving via one link → tampering/noise on that link
Alerts saved to logs/alerts.jsonl.
firewall.py: ordered ACL rules at the SOC entrance (allow/deny by source IP or subnet, destination port, protocol), first match wins, configurable default policy. Blocked packets are counted and logged. Use the ipaddress module for subnet matching.
qos.py: token bucket per sensor (rate and bucket size from config). Frames beyond the rate are dropped and counted; a sensor repeatedly exceeding its rate raises a "flooding" alert. Record allowed vs dropped per second for a chart.

### Phase 5 – Dashboard (HTTP)
Follow the "Design and quality standard" section strictly. Before writing any code, describe the layout of each tab in a few lines and wait for my approval.
Flask app with JSON endpoints polled every 1 s (no websockets). Sidebar tabs:
- Overview: stat tiles (events received, alerts, corrupted frames, retransmissions, firewall blocks), live alert feed with severity colours, token bucket allowed vs dropped chart, UDP vs TCP split.
- Topology: SVG network graph with node names and IPs, current route highlighted, "Fail link" / "Restore link" controls, forwarding table per router.
- Controls: Inject noise (error rate slider), Launch brute force, Launch port scan, Flood from a sensor, switch framing method and CRC type. Each action shows a small confirmation toast.
- Packet Inspector: select a recent event and show it at each layer: application (event JSON) → transport (UDP/TCP, ports) → network (src/dst IP, TTL, path taken) → data link (header, stuffed frame, CRC, in hex and binary).
After building it, review the UI against the design standard yourself and fix anything cluttered or inconsistent before reporting back.

### Phase 6 – FTP, email, diagnostics (Labs Week 11 & 13)
ftp_archive.py: pyftpdlib server (credentials from config, root ./ftp_root); a report generator producing a daily alert summary as .txt and .csv; upload with ftplib. Add a "Reports" tab with a "Generate & upload report" button and a listing of files on the FTP server.
mailer.py: local aiosmtpd server; HIGH/CRITICAL alerts are emailed via smtplib. Add an "Emails" tab showing received alert emails in an inbox-style list.
diagnostics.py: run ping, traceroute/tracert, netstat, ipconfig/ifconfig and arp -a via subprocess with timeouts, from a fixed whitelist only (no free-text commands). Add a "Diagnostics" tab with a target dropdown, command buttons and output in a terminal-style card.
All new tabs follow the design standard.

### Phase 7 – Polish
- README.md: overview, ASCII architecture diagram, setup, running on one PC and on two PCs, demo steps, project structure, screenshots section.
- run_demo.py starts and cleanly stops everything with one command (Ctrl+C shuts down all services gracefully).
- SYLLABUS_MAP.md: table mapping each networking concept to file + function + dashboard tab.
- Experiment CSVs from Phase 2 in results/.
- Final pass across the whole repo: remove anything unused, make naming and formatting consistent, confirm all tests pass.

## Demo the final system must support (3–4 min)
1. Start everything; normal events flow; route S1→R2→SOC highlighted.
2. Launch brute force → HIGH alert appears and an alert email arrives.
3. Inject noise → CRC rejects frames, NAKs trigger retransmissions, stats update.
4. Fail link R2 → Dijkstra reroutes and the highlighted path changes.
5. Flood from one sensor → token bucket drops excess, flooding alert raised; firewall blocks an unknown IP.
6. Generate report → uploaded to FTP and shown in the file list.
7. Run ping and netstat in Diagnostics; open Packet Inspector to walk through the layers.

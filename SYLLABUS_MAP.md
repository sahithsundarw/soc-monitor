# Syllabus map

Where each networking concept lives in the code and where to see it on the dashboard.

| Concept | Lab week | File | Function / class | Dashboard tab |
|---|---|---|---|---|
| Character (byte) stuffing with FLAG/ESC | 9 | `datalink/framing.py` | `byte_stuff`, `byte_destuff`, `add_byte_flags`, `remove_byte_flags` | Controls (switch), Packet Inspector |
| Bit stuffing with the 01111110 flag | 9 | `datalink/framing.py` | `bit_stuff`, `bit_destuff`, `add_bit_flags`, `remove_bit_flags` | Controls (switch), Packet Inspector |
| Stuffing overhead | 9 | `datalink/framing.py`, `datalink/experiment.py` | `stuffing_overhead`, `overhead_rows` | `results/stuffing_overhead.csv` |
| Frame format: FLAG, HEADER, PAYLOAD, CRC, FLAG | 9–10 | `datalink/frame.py` | `encode_frame`, `decode_frame`, `Header` | Packet Inspector (data link) |
| CRC-12 / CRC-16 / CRC-CCITT by mod-2 division | 10 | `datalink/crc.py` | `mod2_divide`, `compute_crc`, `verify_crc` | Controls (switch), Packet Inspector |
| Error injection (line noise) | 10 | `datalink/crc.py`, `datalink/frame.py` | `inject_errors`, `inject_burst`, `LinkSettings.add_noise` | Controls (noise slider), Overview tiles |
| CRC detection-rate experiment | 10 | `datalink/experiment.py` | `crc_detection_rows` | `results/crc_detection.csv` |
| Ping, traceroute/tracert, netstat, ipconfig/ifconfig, arp | 11 | `services/diagnostics.py` | `COMMANDS`, `run_diagnostic` | Diagnostics |
| UDP datagrams vs TCP connections | 12 | `network/transport.py` | `FrameServer`, `send_tcp` | Overview (UDP vs TCP), Packet Inspector (transport) |
| Hop-by-hop forwarding and TTL | 12 | `network/router.py`, `network/node.py` | `Router.handle_frame`, `Node.transmit`, `Node.next_hop` | Packet Inspector (network) |
| Stop-and-Wait ARQ (seq 0/1, ACK, NAK, timeout, retransmit) | 12 | `datalink/arq.py` | `StopAndWaitSender.send`, `StopAndWaitReceiver.is_new`, `make_ack`, `make_nak` | Overview (retransmissions, frames per sensor) |
| Receiver pipeline: flags, destuff, split, CRC, parse | 12 | `soc/collector.py` | `Collector.handle_frame`, `on_corrupted`, `on_data` | Overview (corrupted frames) |
| Sensors as end hosts | 12 | `soc/sensor.py`, `soc/events.py` | `Sensor.send_event`, `EventFactory` | Controls (attacks), Packet Inspector |
| FTP server and client (control + data connections) | 13 | `services/ftp_archive.py` | `FtpArchiveServer`, `upload_files`, `list_files` | Reports |
| Weighted graph topology, link failure | 14 | `network/topology.py` | `Topology.fail_link`, `restore_link`, `set_cost` | Topology |
| Dijkstra shortest path and forwarding tables | 14 | `network/routing.py` | `dijkstra`, `shortest_path`, `build_forwarding_table` | Topology |
| ACL packet filter, first match wins | – | `soc/firewall.py` | `Rule.matches`, `Firewall.decide` | Overview (firewall blocks), alerts |
| Token bucket rate limiting | – | `soc/qos.py` | `TokenBucket.allow`, `TrafficPolicer` | Overview (token bucket chart) |
| Intrusion detection with sliding windows | – | `soc/detector.py` | `Detector.process_event`, `record_crc_failure` | Overview (live alerts) |
| SMTP (EHLO, MAIL FROM, RCPT TO, DATA) | – | `services/mailer.py` | `MailServer`, `send_email`, `AlertMailer` | Emails |
| HTTP: JSON polling and POST actions | – | `dashboard/app.py` | `create_app`, `register_api` | every tab |
| Encapsulation across layers | – | `dashboard/inspector.py` | `describe_layers` | Packet Inspector |

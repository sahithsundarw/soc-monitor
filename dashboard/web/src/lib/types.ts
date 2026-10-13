// Shapes of the Flask JSON API (dashboard/app.py). Every response is wrapped in
// {"data": ..., "error": null | "message"}; these types describe `data`.

export const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const
export type Severity = (typeof SEVERITIES)[number]

export const TILES = [
  "events",
  "alerts",
  "corrupted",
  "retransmissions",
  "firewall_blocks",
] as const
export type Tile = (typeof TILES)[number]

export type Alert = {
  ts: number
  rule: string
  source: string
  severity: Severity
  title: string
  detail: string
}

export type FrameCounts = {
  good: number
  corrupted: number
  retransmitted: number
  lost: number
}

export type Route = { path: string[]; cost: number | null }

export type QosSecond = { t: number; allowed: number; dropped: number }

export type LinkSettings = {
  method: string
  crc_type: string
  error_rate: number
}

export type Status = {
  running: boolean
  tiles: Record<Tile, number>
  lost: number
  trends: Record<Tile, number[]>
  severity_counts: Record<Severity, number>
  uptime_s: number | null
  email_count: number
  alerts: Alert[]
  protocols: { udp: number; tcp: number }
  per_sensor: Record<string, { udp: FrameCounts; tcp: FrameCounts }>
  qos: { timeline: QosSecond[]; totals: Record<string, unknown> }
  routes: Record<string, Route>
  settings: LinkSettings
}

export type Meta = {
  sensors: string[]
  methods: string[]
  crc_types: string[]
  ftp_address: string
}

export type TopologyNode = {
  id: string
  name: string
  role: string
  sim_ip: string
  x: number
  y: number
}

export type Link = { a: string; b: string; cost: number; up: boolean }

export type Topology = {
  nodes: TopologyNode[]
  links: Link[]
  routes: Record<string, Route>
  tables: Record<string, Record<string, string>>
  destinations: string[]
}

export type EventSummary = {
  id: string
  received_at: number
  sensor: string
  type: string
  protocol: string
}

export type Layers = {
  id: string
  application: { json: string }
  transport: {
    protocol: string
    src_port: number
    dst_port: number
    note: string
  }
  network: {
    src_ip: string
    dst_ip: string
    ttl: number
    hops: number
    path: string[]
    priority: number
  }
  datalink: {
    method: string
    crc_type: string
    header_text: string
    frame_type: string
    seq_no: number
    crc_hex: string
    crc_bits: string
    body_bytes: number
    wire_bytes: number
    wire_hex: string
    wire_binary: string
  }
}

export type ReportFile = { name: string; size: number; modified: string }

export type Email = {
  id: number
  subject: string
  sender: string
  recipient: string
  received_at: number
  body: string
}

export type DiagnosticCommand = {
  id: string
  label: string
  summary: string
  needs_target: boolean
}

export type Diagnostics = {
  commands: DiagnosticCommand[]
  targets: { label: string; ip: string }[]
}

export type DiagnosticResult = {
  command: string
  output: string
  returncode: number | null
}

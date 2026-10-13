import {
  ArchiveIcon,
  LayersIcon,
  LayoutDashboardIcon,
  MailIcon,
  NetworkIcon,
  SlidersHorizontalIcon,
  SquareTerminalIcon,
  type LucideIcon,
} from "lucide-react"

/** Sidebar groups, in order: watching the network, acting on it, its services. */
export const TAB_GROUPS = ["Monitor", "Operate", "Services"] as const

export const TABS = [
  {
    id: "overview",
    title: "Overview",
    group: "Monitor",
    icon: LayoutDashboardIcon,
  },
  { id: "topology", title: "Topology", group: "Monitor", icon: NetworkIcon },
  {
    id: "inspector",
    title: "Packet Inspector",
    group: "Monitor",
    icon: LayersIcon,
  },
  {
    id: "controls",
    title: "Controls",
    group: "Operate",
    icon: SlidersHorizontalIcon,
  },
  {
    id: "diagnostics",
    title: "Diagnostics",
    group: "Operate",
    icon: SquareTerminalIcon,
  },
  { id: "reports", title: "Reports", group: "Services", icon: ArchiveIcon },
  { id: "emails", title: "Emails", group: "Services", icon: MailIcon },
] as const satisfies readonly {
  id: string
  title: string
  group: (typeof TAB_GROUPS)[number]
  icon: LucideIcon
}[]

export type TabId = (typeof TABS)[number]["id"]

export function isTabId(value: string): value is TabId {
  return TABS.some((tab) => tab.id === value)
}

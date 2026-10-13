import { Badge } from "@/components/ui/badge"
import { SEVERITY_NAMES } from "@/lib/format"
import type { Severity } from "@/lib/types"

const VARIANTS = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
} as const satisfies Record<Severity, string>

/** An alert's severity as a tinted pill, the only place severity colours appear. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge variant={VARIANTS[severity]}>{SEVERITY_NAMES[severity]}</Badge>
}

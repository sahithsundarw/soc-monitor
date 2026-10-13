import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export type KeyValue = { label: string; value: ReactNode; mono?: boolean }

/** A two-column label/value list (dl), labels muted, values left aligned. */
export function KeyValues({
  items,
  className,
}: {
  items: KeyValue[]
  className?: string
}) {
  return (
    <dl
      className={cn(
        "grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-6 gap-y-2 text-sm",
        className
      )}
    >
      {items.map((item) => (
        <div key={item.label} className="contents">
          <dt className="text-muted-foreground">{item.label}</dt>
          <dd className={cn("min-w-0 break-words", item.mono && "font-mono")}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

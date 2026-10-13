import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** The large page title with the page's main actions on the right. */
export function PageHeader({
  title,
  actions,
}: {
  title: string
  actions?: ReactNode
}) {
  return (
    <div className="flex min-h-24 flex-wrap items-center justify-between gap-4 border-b px-4 py-6 md:px-6">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  )
}

export function PageBody({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-8 p-4 md:p-6">
      {children}
    </div>
  )
}

/** A titled block of the page; no box, sections are separated by space. */
export function Section({
  title,
  actions,
  children,
  className,
}: {
  title: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("flex min-w-0 flex-col gap-4", className)}>
      <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {actions && (
          <div className="flex max-w-full flex-wrap items-center gap-3">
            {actions}
          </div>
        )}
      </div>
      {children}
    </section>
  )
}

/** A bordered box for tables, the graph and terminal output. */
export function Panel({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "min-w-0 overflow-hidden rounded-lg border bg-card",
        className
      )}
    >
      {children}
    </div>
  )
}

import { CopyIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success("Copied to the clipboard")
  } catch {
    toast.error("Copy is not available here. Select the text instead.")
  }
}

/** Monospace text (hex, binary, JSON) with an optional copy button. */
export function CodeBlock({
  label,
  text,
  copyable = false,
  scroll = false,
}: {
  label?: string
  text: string
  copyable?: boolean
  /** Cap the height and scroll (for long hex/binary dumps). */
  scroll?: boolean
}) {
  return (
    <div className="flex flex-col gap-1">
      {(label || copyable) && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-muted-foreground">{label}</span>
          {copyable && (
            <Button
              variant="ghost"
              onClick={() => copyText(text)}
              aria-label={`Copy ${label?.toLowerCase() ?? "text"}`}
            >
              <CopyIcon data-icon="inline-start" />
              Copy
            </Button>
          )}
        </div>
      )}
      <pre
        className={cn(
          "overflow-auto rounded-lg border bg-terminal p-3 font-mono text-sm leading-relaxed break-all whitespace-pre-wrap",
          scroll && "max-h-48"
        )}
      >
        {text}
      </pre>
    </div>
  )
}

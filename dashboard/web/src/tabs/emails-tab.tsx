import { useState } from "react"
import { MailIcon, MailOpenIcon } from "lucide-react"

import { KeyValues } from "@/components/key-values"
import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { PanelEmpty } from "@/components/panel-empty"
import { SeverityBadge } from "@/components/severity-badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { useHoverHold } from "@/hooks/use-hover-hold"
import { usePoll } from "@/hooks/use-poll"
import { formatTime, splitSubject } from "@/lib/format"
import type { Email } from "@/lib/types"
import { cn } from "@/lib/utils"

const POLL_MS = 1000

function Inbox({
  mails,
  selected,
  onSelect,
}: {
  mails: Email[]
  selected: number | null
  onSelect: (mail: Email) => void
}) {
  const { shown, holdProps } = useHoverHold(mails)
  return (
    <ScrollArea
      className="[&>[data-slot=scroll-area-viewport]]:max-h-[36rem]"
      {...holdProps}
    >
      <ul aria-label="Alert emails" className="flex flex-col">
        {shown.map((mail) => {
          const { severity, title } = splitSubject(mail.subject)
          const isSelected = mail.id === selected
          return (
            <li key={mail.id} className="border-b last:border-b-0">
              <button
                type="button"
                aria-current={isSelected || undefined}
                onClick={() => onSelect(mail)}
                className={cn(
                  "grid w-full grid-cols-[5.5rem_1fr_auto] items-center gap-3 px-4 py-3 text-left text-sm transition-colors outline-none hover:bg-muted/50 focus-visible:bg-muted",
                  isSelected && "bg-muted hover:bg-muted"
                )}
              >
                {severity ? <SeverityBadge severity={severity} /> : <span />}
                <span className={cn("truncate", isSelected && "font-medium")}>
                  {title}
                </span>
                <span className="font-mono text-muted-foreground tabular-nums">
                  {formatTime(mail.received_at)}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </ScrollArea>
  )
}

function Reader({ mail }: { mail: Email }) {
  return (
    <div className="flex flex-col gap-4">
      <KeyValues
        items={[
          { label: "From", value: mail.sender, mono: true },
          { label: "To", value: mail.recipient, mono: true },
          {
            label: "Received",
            value: formatTime(mail.received_at),
            mono: true,
          },
        ]}
      />
      <pre className="rounded-lg border bg-terminal p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
        {mail.body}
      </pre>
    </div>
  )
}

export function EmailsTab({ active }: { active: boolean }) {
  const poll = usePoll<Email[]>("/api/emails", POLL_MS, { enabled: active })
  const [selected, setSelected] = useState<Email | null>(null)

  return (
    <>
      <PageHeader title="Emails" />
      <PageBody>
        <div className="grid items-start gap-8 lg:grid-cols-12">
          <Section title="Inbox" className="lg:col-span-5">
            <Panel>
              {!poll.data ? (
                <div className="flex flex-col gap-3 p-4">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : poll.data.length === 0 ? (
                <PanelEmpty
                  icon={MailIcon}
                  title="No alert emails yet"
                  description="High and critical alerts are emailed here."
                />
              ) : (
                <Inbox
                  mails={poll.data}
                  selected={selected?.id ?? null}
                  onSelect={setSelected}
                />
              )}
            </Panel>
          </Section>
          <Section
            title={selected ? splitSubject(selected.subject).title : "Message"}
            className="lg:col-span-7"
          >
            <Panel className="p-4 md:p-6">
              {selected ? (
                <Reader mail={selected} />
              ) : (
                <PanelEmpty
                  icon={MailOpenIcon}
                  title="No email selected"
                  description="Select an email to read it."
                />
              )}
            </Panel>
          </Section>
        </div>
      </PageBody>
    </>
  )
}

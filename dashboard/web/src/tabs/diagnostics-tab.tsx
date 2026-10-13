import { useState } from "react"

import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useAction } from "@/hooks/use-action"
import { usePoll } from "@/hooks/use-poll"
import { api } from "@/lib/api"
import type {
  DiagnosticCommand,
  DiagnosticResult,
  Diagnostics,
} from "@/lib/types"

type Terminal = { title: string; meta: string; text: string }

const IDLE: Terminal = {
  title: "Output",
  meta: "",
  text: "Pick a command to run it here.",
}

function shortLabel(command: DiagnosticCommand): string {
  return command.label.replace(" (SOC Monitor ports)", "")
}

/** Await `work` and report how long it took, in seconds with one decimal. */
async function timed<T>(
  work: () => Promise<T>
): Promise<{ result: T; seconds: string }> {
  const started = performance.now()
  const result = await work()
  return { result, seconds: ((performance.now() - started) / 1000).toFixed(1) }
}

export function DiagnosticsTab({ active }: { active: boolean }) {
  const options = usePoll<Diagnostics>("/api/diagnostics", 2000, {
    once: true,
    enabled: active,
  })
  const [target, setTarget] = useState<string>()
  const [terminal, setTerminal] = useState<Terminal>(IDLE)
  const { pending, busy, run } = useAction()
  const chosenTarget = target ?? options.data?.targets[0]?.ip ?? ""

  const runCommand = async (command: DiagnosticCommand) => {
    setTerminal({ title: command.label, meta: "running…", text: "Running…" })
    const { result, seconds } = await timed(() =>
      run(
        command.id,
        () =>
          api<DiagnosticResult>("/api/diagnostics", {
            command: command.id,
            target: chosenTarget,
          }),
        `${command.label} finished`
      )
    )
    if (result) {
      const exit =
        result.returncode === null ? "timed out" : `exit ${result.returncode}`
      setTerminal({
        title: command.label,
        meta: `${exit}, ${seconds} s`,
        text: `$ ${result.command}\n\n${result.output}`,
      })
    } else {
      setTerminal({
        title: command.label,
        meta: "",
        text: "The command could not run. See the message in the corner.",
      })
    }
  }

  return (
    <>
      <PageHeader title="Diagnostics" />
      <PageBody>
        <Section title="Network commands">
          {!options.data ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <div className="flex flex-wrap items-end gap-4">
              <Field className="w-auto">
                <FieldLabel htmlFor="diag-target">Target</FieldLabel>
                <Select value={chosenTarget} onValueChange={setTarget}>
                  <SelectTrigger id="diag-target" className="min-w-64">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {options.data.targets.map((entry) => (
                        <SelectItem key={entry.ip} value={entry.ip}>
                          {entry.label}{" "}
                          <span className="font-mono text-muted-foreground">
                            {entry.ip}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <div className="flex flex-wrap gap-2">
                {options.data.commands.map((command) => (
                  <Tooltip key={command.id}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() => runCommand(command)}
                      >
                        {pending.has(command.id) && (
                          <Spinner data-icon="inline-start" />
                        )}
                        {shortLabel(command)}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>{command.summary}</TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </div>
          )}
          <Panel>
            <div className="flex items-center justify-between gap-4 border-b px-4 py-3 text-sm">
              <span className="font-medium">{terminal.title}</span>
              <span className="font-mono text-muted-foreground">
                {terminal.meta}
              </span>
            </div>
            <pre
              aria-live="polite"
              className="max-h-[32rem] min-h-64 overflow-auto bg-terminal p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap"
            >
              {terminal.text}
            </pre>
          </Panel>
        </Section>
      </PageBody>
    </>
  )
}

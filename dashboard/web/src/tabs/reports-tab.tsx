import { FolderOpenIcon, ServerCrashIcon, UploadIcon } from "lucide-react"

import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { PanelEmpty } from "@/components/panel-empty"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useAction } from "@/hooks/use-action"
import { usePoll } from "@/hooks/use-poll"
import { api } from "@/lib/api"
import { formatBytes } from "@/lib/format"
import type { ReportFile } from "@/lib/types"

const SLOW_POLL_MS = 5000

function FileTable({ files }: { files: ReportFile[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Modified</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {files.map((file) => (
          <TableRow key={file.name}>
            <TableCell className="font-mono">{file.name}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatBytes(file.size)}
            </TableCell>
            <TableCell className="font-mono text-muted-foreground">
              {file.modified}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ServerFacts({ items }: { items: [string, string][] }) {
  return (
    <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="flex items-baseline gap-2">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-mono">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ReportsTab({ ftpAddress }: { ftpAddress: string | undefined }) {
  const poll = usePoll<ReportFile[]>("/api/reports", SLOW_POLL_MS)
  const { pending, run } = useAction()
  const files = poll.data

  const generate = async () => {
    const done = await run(
      "report",
      () => api<{ uploaded: string[] }>("/api/reports", {}),
      (data) => `Uploaded ${data.uploaded.join(" and ")}`
    )
    if (done) poll.refresh()
  }

  return (
    <>
      <PageHeader
        title="Reports"
        actions={
          <Button onClick={generate} disabled={pending !== null}>
            {pending ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <UploadIcon data-icon="inline-start" />
            )}
            Generate &amp; upload report
          </Button>
        }
      />
      <PageBody>
        <Section
          title="FTP archive"
          actions={
            <ServerFacts
              items={[
                ["Server", ftpAddress ?? "–"],
                // The listing is newest first, so its first file is the latest upload.
                [
                  "Last upload",
                  !files ? "–" : files.length ? files[0].modified : "never",
                ],
              ]}
            />
          }
        >
          {poll.error && (
            <Alert variant="destructive">
              <ServerCrashIcon />
              <AlertTitle>FTP archive unavailable</AlertTitle>
              <AlertDescription>{poll.error}</AlertDescription>
            </Alert>
          )}
          {!files ? (
            !poll.error && <Skeleton className="h-32 w-full" />
          ) : (
            <Panel>
              {files.length === 0 ? (
                <PanelEmpty
                  icon={FolderOpenIcon}
                  title="No files uploaded yet"
                  description="Generate a report to upload today's alert summary."
                />
              ) : (
                <FileTable files={files} />
              )}
            </Panel>
          )}
        </Section>
      </PageBody>
    </>
  )
}

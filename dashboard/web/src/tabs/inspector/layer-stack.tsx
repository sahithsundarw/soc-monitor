import type { ReactNode } from "react"

import { CodeBlock } from "@/components/code-block"
import { KeyValues } from "@/components/key-values"
import { METHOD_NAMES, plural, routeText } from "@/lib/format"
import type { Layers } from "@/lib/types"

const PRIORITIES = ["normal", "high", "critical"]

/** One OSI layer: its number on a rail that connects the stack top to bottom. */
function Layer({
  number,
  title,
  children,
}: {
  number: number
  title: string
  children: ReactNode
}) {
  return (
    <li className="group/layer relative grid grid-cols-[2rem_1fr] gap-x-4 pb-6 last:pb-0">
      <span
        aria-hidden
        className="absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 bg-border group-last/layer:hidden"
      />
      <span className="flex size-8 items-center justify-center rounded-lg border bg-muted font-mono text-sm font-medium">
        {number}
      </span>
      <div className="flex min-w-0 flex-col gap-3 pt-1">
        <h3 className="font-medium">
          <span className="sr-only">Layer {number}, </span>
          {title}
        </h3>
        {children}
      </div>
    </li>
  )
}

/** A received event walked down the stack: application → transport →
 * network → data link, ending with the stuffed frame as it was on the wire. */
export function LayerStack({ layers }: { layers: Layers }) {
  const { application, transport, network, datalink } = layers
  return (
    <ol className="flex flex-col">
      <Layer number={7} title="Application">
        <CodeBlock text={application.json} />
      </Layer>
      <Layer number={4} title="Transport">
        <KeyValues
          items={[
            { label: "Protocol", value: transport.protocol },
            { label: "Source port", value: transport.src_port, mono: true },
            {
              label: "Destination port",
              value: transport.dst_port,
              mono: true,
            },
            { label: "Delivery", value: transport.note },
          ]}
        />
      </Layer>
      <Layer number={3} title="Network">
        <KeyValues
          items={[
            { label: "Source IP", value: network.src_ip, mono: true },
            { label: "Destination IP", value: network.dst_ip, mono: true },
            {
              label: "TTL on arrival",
              value: `${network.ttl}, after ${network.hops} router ${plural(network.hops, "hop")}`,
            },
            {
              label: "Path taken",
              value: network.path.length ? routeText(network.path) : "unknown",
              mono: true,
            },
            {
              label: "Priority",
              value: `${network.priority} (${PRIORITIES[network.priority] ?? "unknown"})`,
            },
          ]}
        />
      </Layer>
      <Layer number={2} title="Data link">
        <KeyValues
          items={[
            {
              label: "Framing",
              value: METHOD_NAMES[datalink.method] ?? datalink.method,
            },
            { label: "CRC", value: datalink.crc_type },
            { label: "Header", value: datalink.header_text, mono: true },
            {
              label: "Frame type, seq",
              value: `${datalink.frame_type}, ${datalink.seq_no}`,
            },
            {
              label: "CRC remainder",
              value: `${datalink.crc_hex} (${datalink.crc_bits})`,
              mono: true,
            },
            {
              label: "Size",
              value: `${datalink.body_bytes} bytes before stuffing, ${datalink.wire_bytes} on the wire`,
            },
          ]}
        />
        <CodeBlock
          label="Stuffed frame with flags, hex"
          text={datalink.wire_hex}
          copyable
          scroll
        />
        <CodeBlock
          label="Stuffed frame with flags, binary"
          text={datalink.wire_binary}
          copyable
          scroll
        />
      </Layer>
    </ol>
  )
}

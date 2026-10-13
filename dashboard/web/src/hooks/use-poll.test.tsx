import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { usePoll } from "@/hooks/use-poll"

function reply(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body)))
}

/** Let pending promises settle, then move the fake clock. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe("usePoll", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  it("fetches now and again every interval", async () => {
    fetchMock.mockImplementation(() => reply({ data: { n: 1 }, error: null }))
    const { result } = renderHook(() =>
      usePoll<{ n: number }>("/api/status", 1000)
    )
    await advance(0)
    expect(result.current.data).toEqual({ n: 1 })
    expect(result.current.lastUpdate).toBeGreaterThan(0)
    await advance(1000)
    await advance(1000)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it("keeps the last data on failure and clears the error on recovery", async () => {
    fetchMock
      .mockImplementationOnce(() => reply({ data: "first", error: null }))
      .mockImplementationOnce(() =>
        Promise.reject(new TypeError("Failed to fetch"))
      )
      .mockImplementation(() => reply({ data: "back", error: null }))
    const { result } = renderHook(() => usePoll<string>("/api/status", 1000))
    await advance(0)
    await advance(1000)
    expect(result.current.data).toBe("first")
    expect(result.current.error).toBe("Failed to fetch")
    await advance(1000)
    expect(result.current.data).toBe("back")
    expect(result.current.error).toBeNull()
  })

  it("shows the server's error message", async () => {
    fetchMock.mockImplementation(() =>
      reply({ data: null, error: "FTP server not reachable" })
    )
    const { result } = renderHook(() => usePoll("/api/reports", 5000))
    await advance(0)
    expect(result.current.error).toBe("FTP server not reachable")
  })

  it("with once, stops after the first success", async () => {
    fetchMock
      .mockImplementationOnce(() =>
        Promise.reject(new TypeError("Failed to fetch"))
      )
      .mockImplementation(() => reply({ data: [], error: null }))
    renderHook(() => usePoll("/api/meta", 1000, { once: true }))
    await advance(0)
    await advance(1000)
    await advance(5000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("runs one loop under StrictMode's mount, unmount, mount", async () => {
    fetchMock.mockImplementation(() => reply({ data: 1, error: null }))
    renderHook(() => usePoll("/api/status", 1000), { reactStrictMode: true })
    await advance(0)
    const afterMount = fetchMock.mock.calls.length
    await advance(3000)
    // Exactly one request per second after the initial one(s).
    expect(fetchMock.mock.calls.length - afterMount).toBe(3)
  })

  it("pauses while disabled and fetches right away when enabled again", async () => {
    fetchMock.mockImplementation(() => reply({ data: 1, error: null }))
    const { rerender } = renderHook(
      ({ enabled }) => usePoll("/api/topology", 1000, { enabled }),
      { initialProps: { enabled: false } }
    )
    await advance(3000)
    expect(fetchMock).not.toHaveBeenCalled()
    rerender({ enabled: true })
    await advance(0)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    rerender({ enabled: false })
    await advance(3000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("stops polling when unmounted", async () => {
    fetchMock.mockImplementation(() => reply({ data: 1, error: null }))
    const { unmount } = renderHook(() => usePoll("/api/events", 1000))
    await advance(0)
    unmount()
    await advance(5000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

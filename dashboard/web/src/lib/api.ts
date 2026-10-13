// The one way the dashboard talks to Flask: GET to read, POST (JSON) to act.

/** The server answered, but with {"error": "..."}; the message is for people. */
export class ApiError extends Error {}

export async function api<T>(path: string, payload?: unknown): Promise<T> {
  const options: RequestInit =
    payload === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
  const response = await fetch(path, options)
  let body: { data: T; error: string | null }
  try {
    body = await response.json()
  } catch {
    throw new ApiError(
      `The server sent an unreadable reply (HTTP ${response.status})`
    )
  }
  if (body.error) throw new ApiError(body.error)
  return body.data
}

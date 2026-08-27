const API_BASE = '/api/v1'

interface ApiOptions {
  method?: string
  token?: string | null
  body?: unknown
  timeoutMs?: number
}

function parseErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string')
    return detail
  if (Array.isArray(detail))
    return detail.map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : JSON.stringify(item))).join('; ')
  return fallback
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', token, body, timeoutMs = 6000 } = options
  const headers: Record<string, string> = {}
  if (token)
    headers.Authorization = `Bearer ${token}`
  if (body !== undefined)
    headers['Content-Type'] = 'application/json'

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      signal: controller.signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    clearTimeout(timer)

    const text = await response.text()
    let data: Record<string, unknown> = {}
    try {
      data = text ? JSON.parse(text) as Record<string, unknown> : {}
    }
    catch {
      data = { detail: text }
    }

    if (!response.ok) {
      throw new Error(parseErrorDetail(data.detail, data.message as string || response.statusText || `请求失败 (${response.status})`))
    }

    return data as T
  }
  catch (error) {
    clearTimeout(timer)
    if (error instanceof DOMException && error.name === 'AbortError')
      throw new Error('请求超时，请检查后端网络连接')
    throw error
  }
}

export { API_BASE }

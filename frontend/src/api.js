// Тънка обвивка около fetch: бисквитка за вход + CSRF хедър при променящи заявки.

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

function cookie(name) {
  const row = document.cookie.split('; ').find((c) => c.startsWith(name + '='))
  return row ? decodeURIComponent(row.slice(name.length + 1)) : null
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') {
    const csrf = cookie('kk_csrf')
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  const res = await fetch('/api/v1' + path, {
    method,
    headers,
    credentials: 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const isJson = (res.headers.get('content-type') || '').includes('json')
  const data = isJson ? await res.json() : null
  if (!res.ok) {
    let msg = data?.detail
    if (Array.isArray(msg)) msg = msg.map((e) => `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
    if (res.status === 401 && path !== '/auth/login') onUnauthorized()
    throw new ApiError(res.status, msg || `Грешка ${res.status}`)
  }
  return data
}

export const csvUrl = (path) => '/api/v1' + path

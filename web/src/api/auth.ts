import { api } from '@/api/client'
import type { GuestSessionResponse, RegisterResponse, SessionRecord, TokenResponse, User } from '@/types'

export function login(email: string, password: string) {
  return api<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  })
}

export function register(email: string, password: string, username?: string | null) {
  return api<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: { email, password, username: username || null },
  })
}

export function fetchCurrentUser(token: string) {
  return api<User>('/auth/me', { token })
}

export function createGuestSession() {
  return api<GuestSessionResponse>('/auth/guest', { method: 'POST' })
}

export function createUserSession(token: string) {
  return api<GuestSessionResponse>('/auth/session', { method: 'POST', token })
}

export function listUserSessions(token: string) {
  return api<SessionRecord[]>('/auth/sessions', { token })
}

export function deleteSession(sessionId: string, token: string) {
  return api<{ ok?: boolean }>(`/auth/session/${sessionId}`, { method: 'DELETE', token })
}

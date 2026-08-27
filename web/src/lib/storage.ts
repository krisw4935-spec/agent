import type { User } from '@/types'

const KEYS = {
  userToken: 'mt_user_token',
  currentUser: 'mt_current_user',
  sessionToken: 'mt_session_token',
  sessionId: 'mt_session_id',
} as const

export const storage = {
  get userToken(): string | null {
    return localStorage.getItem(KEYS.userToken)
  },
  set userToken(value: string | null) {
    if (value)
      localStorage.setItem(KEYS.userToken, value)
    else
      localStorage.removeItem(KEYS.userToken)
  },

  get currentUser(): User | null {
    try {
      return JSON.parse(localStorage.getItem(KEYS.currentUser) || 'null') as User | null
    }
    catch {
      return null
    }
  },
  set currentUser(value: User | null) {
    if (value)
      localStorage.setItem(KEYS.currentUser, JSON.stringify(value))
    else
      localStorage.removeItem(KEYS.currentUser)
  },

  get sessionToken(): string | null {
    return localStorage.getItem(KEYS.sessionToken)
  },
  set sessionToken(value: string | null) {
    if (value)
      localStorage.setItem(KEYS.sessionToken, value)
    else
      localStorage.removeItem(KEYS.sessionToken)
  },

  get sessionId(): string | null {
    return localStorage.getItem(KEYS.sessionId)
  },
  set sessionId(value: string | null) {
    if (value)
      localStorage.setItem(KEYS.sessionId, value)
    else
      localStorage.removeItem(KEYS.sessionId)
  },

  clearSession() {
    this.sessionToken = null
    this.sessionId = null
  },

  clearAuth() {
    this.userToken = null
    this.currentUser = null
    this.clearSession()
  },
}

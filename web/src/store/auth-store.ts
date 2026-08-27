import { create } from 'zustand'
import {
  createUserSession,
  deleteSession as deleteSessionApi,
  fetchCurrentUser,
  listUserSessions,
  login as loginApi,
  register as registerApi,
} from '@/api/auth'
import { storage } from '@/lib/storage'
import type { SessionRecord, User } from '@/types'

interface AuthState {
  user: User | null
  userToken: string | null
  sessionToken: string | null
  sessionId: string | null
  sessions: SessionRecord[]
  sessionTitle: string
  authModalOpen: boolean
  authError: string | null
  booting: boolean
  bootError: string | null
  hydrateFromStorage: () => void
  setAuthModalOpen: (open: boolean) => void
  setAuthError: (message: string | null) => void
  setSessionTitle: (title: string) => void
  refreshCurrentUser: () => Promise<User | null>
  loadSessions: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, username?: string | null) => Promise<void>
  logout: () => void
  createSession: () => Promise<SessionRecord>
  switchSession: (session: SessionRecord) => void
  deleteSession: (sessionId: string) => Promise<void>
  setSessionCredentials: (sessionId: string, token: string) => void
  finishBoot: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: storage.currentUser,
  userToken: storage.userToken,
  sessionToken: storage.sessionToken,
  sessionId: storage.sessionId,
  sessions: [],
  sessionTitle: 'Math Teacher 辅导室',
  authModalOpen: false,
  authError: null,
  booting: true,
  bootError: null,

  hydrateFromStorage() {
    set({
      user: storage.currentUser,
      userToken: storage.userToken,
      sessionToken: storage.sessionToken,
      sessionId: storage.sessionId,
    })
  },

  setAuthModalOpen(open) {
    set({ authModalOpen: open, authError: open ? get().authError : null })
  },

  setAuthError(message) {
    set({ authError: message })
  },

  setSessionTitle(title) {
    set({ sessionTitle: title })
  },

  async refreshCurrentUser() {
    const token = get().userToken
    if (!token) {
      storage.currentUser = null
      set({ user: null })
      return null
    }

    try {
      const user = await fetchCurrentUser(token)
      storage.currentUser = user
      set({ user })
      return user
    }
    catch {
      storage.userToken = null
      storage.currentUser = null
      set({ user: null, userToken: null })
      return null
    }
  },

  async loadSessions() {
    const token = get().userToken
    if (!token) {
      set({ sessions: [] })
      return
    }

    const list = await listUserSessions(token)
    set({ sessions: Array.isArray(list) ? list : [] })
  },

  async login(email, password) {
    const response = await loginApi(email, password)
    storage.userToken = response.access_token
    set({ userToken: response.access_token, authError: null })
    await get().refreshCurrentUser()
    await get().loadSessions()
    set({ authModalOpen: false })
  },

  async register(email, password, username) {
    const response = await registerApi(email, password, username)
    storage.userToken = response.token.access_token
    storage.currentUser = {
      id: response.id,
      email: response.email,
      username: response.username,
    }
    set({
      userToken: response.token.access_token,
      user: storage.currentUser,
      authError: null,
      authModalOpen: false,
    })
  },

  logout() {
    storage.clearAuth()
    set({
      user: null,
      userToken: null,
      sessionToken: null,
      sessionId: null,
      sessions: [],
      sessionTitle: 'Math Teacher 辅导室',
      authModalOpen: true,
    })
  },

  async createSession() {
    const token = get().userToken
    if (!token)
      throw new Error('请先登录')

    const session = await createUserSession(token)
    storage.sessionToken = session.token.access_token
    storage.sessionId = session.session_id
    set({
      sessionToken: session.token.access_token,
      sessionId: session.session_id,
      sessionTitle: 'Math Teacher 辅导室',
    })

    const sessions = [session, ...get().sessions]
    set({ sessions })
    return session
  },

  switchSession(session) {
    storage.sessionId = session.session_id
    if (session.token?.access_token)
      storage.sessionToken = session.token.access_token

    set({
      sessionId: session.session_id,
      sessionToken: session.token?.access_token || get().sessionToken,
      sessionTitle: session.name ? `辅导室 · ${session.name}` : 'Math Teacher 辅导室',
    })
  },

  setSessionCredentials(sessionId, token) {
    storage.sessionId = sessionId
    storage.sessionToken = token
    set({ sessionId, sessionToken: token })
  },

  async deleteSession(sessionId) {
    const authToken = get().userToken || get().sessionToken
    if (!authToken)
      return

    await deleteSessionApi(sessionId, authToken)
    const sessions = get().sessions.filter(item => item.session_id !== sessionId)
    set({ sessions })

    if (get().sessionId === sessionId) {
      if (sessions.length > 0)
        get().switchSession(sessions[0])
      else
        await get().createSession()
    }
  },

  finishBoot() {
    set({ booting: false, bootError: null })
  },
}))

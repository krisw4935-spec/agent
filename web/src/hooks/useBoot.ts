import { useEffect } from 'react'
import { fetchMessages } from '@/api/chatbot'
import { DEFAULT_GREETING } from '@/lib/format'
import { useAuthStore } from '@/store/auth-store'
import { useChatStore } from '@/store/chat-store'

export function useBoot() {
  const hydrateFromStorage = useAuthStore(state => state.hydrateFromStorage)
  const refreshCurrentUser = useAuthStore(state => state.refreshCurrentUser)
  const loadSessions = useAuthStore(state => state.loadSessions)
  const switchSession = useAuthStore(state => state.switchSession)
  const finishBoot = useAuthStore(state => state.finishBoot)
  const setAuthModalOpen = useAuthStore(state => state.setAuthModalOpen)
  const setMessages = useChatStore(state => state.setMessages)

  useEffect(() => {
    let cancelled = false

    async function boot() {
      hydrateFromStorage()
      const auth = useAuthStore.getState()

      try {
        if (auth.userToken) {
          const user = await refreshCurrentUser()
          if (cancelled)
            return

          if (user) {
            await loadSessions()
            if (cancelled)
              return

            const latestAuth = useAuthStore.getState()
            if (latestAuth.sessionToken && latestAuth.sessionId) {
              try {
                const data = await fetchMessages(latestAuth.sessionToken, 3000)
                if (cancelled)
                  return

                const msgs = data.messages || []
                setMessages(msgs.length ? msgs : [{ role: 'assistant', content: DEFAULT_GREETING }])
                finishBoot()
                return
              }
              catch {
                // fall through to first session
              }
            }

            if (latestAuth.sessions.length > 0) {
              const first = latestAuth.sessions[0]
              switchSession(first)
              const data = await fetchMessages(first.token?.access_token || latestAuth.sessionToken || '', 6000)
              if (cancelled)
                return
              const msgs = data.messages || []
              setMessages(msgs.length ? msgs : [{ role: 'assistant', content: DEFAULT_GREETING }])
              finishBoot()
              return
            }

            await useChatStore.getState().startNewSession()
            finishBoot()
            return
          }
        }

        setMessages([])
        setAuthModalOpen(true)
        finishBoot()
      }
      catch {
        if (!cancelled) {
          setMessages([])
          setAuthModalOpen(true)
          finishBoot()
        }
      }
    }

    void boot()

    return () => {
      cancelled = true
    }
  }, [
    finishBoot,
    hydrateFromStorage,
    loadSessions,
    refreshCurrentUser,
    setAuthModalOpen,
    setMessages,
    switchSession,
  ])
}

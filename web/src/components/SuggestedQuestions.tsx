import clsx from 'clsx'
import { useChatStore } from '@/store/chat-store'
import type { SuggestedQuestion } from '@/types'

function getGradeBadgeStyle(item: SuggestedQuestion, index: number) {
  const grade = item.grade || (
    item.label.includes('小学') || item.prompt.includes('小学') ? '小学'
      : item.label.includes('初中') || item.prompt.includes('初中') ? '初中'
        : item.label.includes('高中') || item.prompt.includes('高中') ? '高中'
          : index === 0 ? '小学'
            : index === 1 ? '初中'
              : index === 2 ? '高中'
                : '综合'
  )

  switch (grade) {
    case '小学':
      return {
        badge: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
        icon: 'i-lucide-book-open',
        text: '小学趣味',
      }
    case '初中':
      return {
        badge: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20',
        icon: 'i-lucide-compass',
        text: '初中进阶',
      }
    case '高中':
      return {
        badge: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
        icon: 'i-lucide-graduation-cap',
        text: '高中探究',
      }
    default:
      return {
        badge: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
        icon: 'i-lucide-lightbulb',
        text: '生活建模',
      }
  }
}

export function SuggestedQuestions() {
  const busy = useChatStore(state => state.busy)
  const suggestedQuestions = useChatStore(state => state.suggestedQuestions)
  const suggestedQuestionsLoading = useChatStore(state => state.suggestedQuestionsLoading)
  const sendMessage = useChatStore(state => state.sendMessage)

  if (!suggestedQuestionsLoading && suggestedQuestions.length === 0)
    return null

  return (
    <div className="pl-12 -mt-1 mb-2 max-w-[min(100%,720px)] w-full">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-2.5 text-xs text-[var(--semi-color-text-2)] font-medium">
        <div className="flex items-center gap-1.5">
          <span className="i-lucide-sparkles text-amber-500 w-3.5 h-3.5" aria-hidden="true" />
          <span>推荐启发式探究题（小学 · 初中 · 高中）</span>
        </div>
        <span className="text-[11px] text-[var(--semi-color-text-3)] hidden sm:inline">点击卡片直接开启辅导</span>
      </div>

      {suggestedQuestionsLoading && suggestedQuestions.length === 0
        ? (
            /* Skeleton Loading Grid */
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
              {[1, 2, 3, 4].map(idx => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl border border-[var(--semi-color-border)] bg-[var(--semi-color-bg-1)] animate-pulse flex flex-col justify-between min-h-[92px]"
                >
                  <div className="flex justify-between items-center">
                    <div className="h-4.5 w-16 bg-[var(--semi-color-fill-1)] rounded-md" />
                    <div className="h-3.5 w-3.5 bg-[var(--semi-color-fill-1)] rounded-full" />
                  </div>
                  <div className="h-4 w-4/5 bg-[var(--semi-color-fill-1)] rounded mt-2.5" />
                  <div className="h-3 w-full bg-[var(--semi-color-fill-1)] rounded mt-1.5 opacity-60" />
                </div>
              ))}
            </div>
          )
        : (
            /* Card Grid */
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
              {suggestedQuestions.map((item, index) => {
                const style = getGradeBadgeStyle(item, index)
                return (
                  <button
                    key={`${item.label}-${index}`}
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      if (!busy)
                        void sendMessage(item.prompt)
                    }}
                    className={clsx(
                      'group relative flex flex-col text-left justify-between p-3.5 rounded-xl border',
                      'bg-[var(--semi-color-bg-1)] hover:bg-[var(--semi-color-bg-2)]',
                      'border-[var(--semi-color-border)] hover:border-[rgba(var(--brand-primary),0.45)]',
                      'shadow-sm hover:shadow-md transition-all duration-200',
                      'hover:-translate-y-0.5 active:translate-y-0',
                      busy ? 'cursor-not-allowed opacity-55' : 'cursor-pointer',
                    )}
                  >
                    {/* Top Row: Grade Badge + Arrow */}
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className={clsx(
                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border',
                          style.badge,
                        )}
                      >
                        <span className={clsx(style.icon, 'w-3 h-3')} aria-hidden="true" />
                        <span>{style.text}</span>
                      </span>
                      <span
                        className="w-3.5 h-3.5 i-lucide-arrow-right text-[var(--semi-color-text-3)] group-hover:text-brand group-hover:translate-x-0.5 transition-all duration-200"
                        aria-hidden="true"
                      />
                    </div>

                    {/* Question Title */}
                    <div className="text-sm font-medium text-[var(--semi-color-text-0)] group-hover:text-brand transition-colors duration-150 line-clamp-1">
                      {item.label}
                    </div>

                    {/* Question Prompt Preview */}
                    <div className="text-xs text-[var(--semi-color-text-2)] mt-1.5 line-clamp-2 leading-relaxed opacity-85 group-hover:opacity-100">
                      {item.prompt}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
    </div>
  )
}

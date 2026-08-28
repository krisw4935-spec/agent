export function escapeHtml(text: string): string {
  if (!text)
    return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

export function formatRelativeTime(isoStr?: string | null): string {
  if (!isoStr)
    return ''
  try {
    let dateStr = String(isoStr).trim()
    if (!dateStr.endsWith('Z') && !/[+-]\d{2}(?::?\d{2})?$/.test(dateStr))
      dateStr += 'Z'

    const date = new Date(dateStr)
    if (Number.isNaN(date.getTime()))
      return ''

    const diffMs = Date.now() - date.getTime()
    if (diffMs < 60000)
      return '刚刚'

    const diffMin = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMin < 60)
      return `${diffMin}分钟前`
    if (diffHours < 24)
      return `${diffHours}小时前`
    if (diffDays < 7)
      return `${diffDays}天前`
    return `${date.getMonth() + 1}/${date.getDate()}`
  }
  catch {
    return ''
  }
}

const TOOL_NAME_MAP: Record<string, string> = {
  router_decision: '题目意图路由与策略规划',
  python_sandbox_execute: 'Python 代码沙箱自验',
  plot_math_function: 'Matplotlib 函数图表绘制',
  render_math_animation: 'Manim 数学动画生成',
  sympy_calculate: 'SymPy 代数精确核算',
  ask_human: '等待用户确认与选择',
  critic_review: 'Critic 双智能体审校与质检',
}

export function getFriendlyToolName(toolName?: string): string {
  if (!toolName)
    return '数学工具演算'
  return TOOL_NAME_MAP[toolName] || toolName
}

export function getToolInputLabel(toolName?: string): string {
  if (toolName === 'critic_review')
    return '📥 审校目标与检查项 (Review Target)'
  if (toolName === 'router_decision')
    return '📥 学生原始输入与上下文 (Student Input)'
  return '📥 输入参数 (Arguments)'
}

export function getToolOutputLabel(toolName?: string): string {
  if (toolName === 'critic_review')
    return '📤 审校结论、思考与评分 (Review Assessment)'
  if (toolName === 'router_decision')
    return '📤 意图分类与路由决策 (Routing Decision)'
  return '📤 执行结果 (Execution Output)'
}

export const DEFAULT_GREETING = '你好！我是 **Math Teacher** 数学导师。\n\n我可以为你：\n- 📈 **图文并茂讲解函数与几何**（自动画图）\n- 🎞️ **生成函数、几何与证明过程的数学动画**\n- ✏️ **批改作业与推导步骤**\n- 🎯 **设计针对性练习题**\n\n点击下方推荐问题开始，或直接输入你的数学问题吧！'

export const WELCOME_AUTH_MESSAGE = '欢迎使用 **Math Teacher** 智能数学导师！\n\n请先登录或注册账号，以使用数学辅导与保存历史记录。'

export const LOGOUT_MESSAGE = '您已退出登录。请重新登录以开启辅导对话与查看历史记录。'



import DOMPurify from 'dompurify'
import katex from 'katex'
import { marked } from 'marked'
import { escapeHtml } from '@/lib/format'
import 'katex/dist/katex.min.css'

interface MathItem {
  id: number
  math: string
  display: boolean
}

function simpleMarkdownFallback(text: string): string {
  if (!text)
    return ''

  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  html = html.replace(/!\[([^\]]*)\]\((data:image\/[^;]+;base64,[^)]+|https?:\/\/[^)]+|\/[^)]+)\)/g, '<img src="$2" alt="$1" />')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>')
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>')
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function renderKatexMath(math: string, isBlock: boolean): string {
  try {
    return katex.renderToString(math, {
      displayMode: isBlock,
      throwOnError: false,
    })
  }
  catch {
    const escaped = escapeHtml(math)
    return isBlock
      ? `<div class="katex-display-fallback">$$${escaped}$$</div>`
      : `<span class="katex-inline-fallback">$${escaped}$</span>`
  }
}

export function parseContent(rawText: string): string {
  if (!rawText)
    return ''

  const mathStore: MathItem[] = []
  let text = String(rawText)

  const codeBlocks: string[] = []
  text = text.replace(/```([\s\S]*?)```/g, (match) => {
    const trimmed = match.trim()
    if (trimmed.startsWith('```math') || trimmed.startsWith('```latex')) {
      const code = trimmed.replace(/^```(?:math|latex)\s*/i, '').replace(/```$/, '').trim()
      const id = mathStore.length
      mathStore.push({ id, math: code, display: true })
      return `\n\n%%MATH_BLOCK_${id}%%\n\n`
    }
    const cid = codeBlocks.length
    codeBlocks.push(match)
    return `%%CODE_BLOCK_${cid}%%`
  })

  const inlineCodes: string[] = []
  text = text.replace(/`([^`\n]+)`/g, (match) => {
    const iid = inlineCodes.length
    inlineCodes.push(match)
    return `%%INLINE_CODE_${iid}%%`
  })

  const images: Array<{ alt: string, url: string }> = []
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, url) => {
    const imgId = images.length
    const cleanAlt = (alt || '').replace(/\$/g, '').trim()
    images.push({ alt: cleanAlt, url: url.trim() })
    return `%%IMG_PLACEHOLDER_${imgId}%%`
  })

  const htmlImgTags: string[] = []
  text = text.replace(/<img[^>]*>/gi, (match) => {
    const hid = htmlImgTags.length
    htmlImgTags.push(match)
    return `%%HTML_IMG_${hid}%%`
  })

  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_match, math) => {
    const id = mathStore.length
    mathStore.push({ id, math: math.trim(), display: true })
    return `\n\n%%MATH_BLOCK_${id}%%\n\n`
  })

  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_match, math) => {
    const id = mathStore.length
    mathStore.push({ id, math: math.trim(), display: true })
    return `\n\n%%MATH_BLOCK_${id}%%\n\n`
  })

  text = text.replace(/(\\begin\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix|vmatrix|cases|split)\*?\}[\s\S]+?\\end\{(?:equation|align|aligned|gather|matrix|pmatrix|bmatrix|vmatrix|cases|split)\*?\})/g, (_match, math) => {
    const id = mathStore.length
    mathStore.push({ id, math: math.trim(), display: true })
    return `\n\n%%MATH_BLOCK_${id}%%\n\n`
  })

  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_match, math) => {
    const id = mathStore.length
    mathStore.push({ id, math: math.trim(), display: false })
    return `%%MATH_INLINE_${id}%%`
  })

  text = text.replace(/(^|[^$])\$([^$\n]+?)\$(?!\$)/g, (match, prefix, math) => {
    const trimmed = math.trim()
    if (!trimmed || math.startsWith(' ') || math.endsWith(' ') || /^\d+(\.\d+)?$/.test(trimmed))
      return match
    const id = mathStore.length
    mathStore.push({ id, math: trimmed, display: false })
    return `${prefix}%%MATH_INLINE_${id}%%`
  })

  text = text.replace(/%%INLINE_CODE_(\d+)%%/g, (_, id) => inlineCodes[Number(id)])
  text = text.replace(/%%CODE_BLOCK_(\d+)%%/g, (_, id) => codeBlocks[Number(id)])
  text = text.replace(/%%IMG_PLACEHOLDER_(\d+)%%/g, (_, id) => {
    const img = images[Number(id)]
    return `![${img.alt}](${img.url})`
  })
  text = text.replace(/%%HTML_IMG_(\d+)%%/g, (_, id) => htmlImgTags[Number(id)])

  let html = ''
  try {
    html = marked.parse(text, { breaks: true, gfm: true }) as string
  }
  catch {
    html = simpleMarkdownFallback(text)
  }

  html = DOMPurify.sanitize(html, {
    ADD_TAGS: [
      'math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 'mi', 'mspace',
      'mover', 'munder', 'msup', 'msub', 'msubsup', 'mfrac', 'mroot', 'msqrt',
      'mtable', 'mtr', 'mtd', 'span', 'div', 'svg', 'path', 'line',
    ],
    ADD_ATTR: [
      'data-*', 'target', 'src', 'alt', 'class', 'style', 'aria-hidden', 'aria-label',
      'viewBox', 'width', 'height', 'xmlns', 'preserveAspectRatio', 'd', 'fill', 'stroke',
    ],
  })

  mathStore.forEach((item) => {
    const rendered = renderKatexMath(item.math, item.display)
    if (item.display) {
      const blockRegex = new RegExp(`<p>\\s*%%MATH_BLOCK_${item.id}%%\\s*<\\/p>|%%MATH_BLOCK_${item.id}%%`, 'g')
      html = html.replace(blockRegex, rendered)
    }
    else {
      const inlineRegex = new RegExp(`%%MATH_INLINE_${item.id}%%`, 'g')
      html = html.replace(inlineRegex, rendered)
    }
  })

  return html
}

export function extractThinkingFromContent(content: string): { thinking: string, content: string } {
  if (!content.includes('<think>'))
    return { thinking: '', content }

  const thinkMatch = content.match(/<think>([\s\S]*?)(?:<\/think>|$)/)
  if (!thinkMatch?.[1])
    return { thinking: '', content }

  return {
    thinking: thinkMatch[1].trim(),
    content: content.replace(/<think>[\s\S]*?(?:<\/think>|$)/, '').trim(),
  }
}

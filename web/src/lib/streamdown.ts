import { code } from '@streamdown/code'
import { createMathPlugin } from '@streamdown/math'

function isLineStart(text: string, index: number): boolean {
  return index === 0 || text[index - 1] === '\n'
}

function getFenceAt(text: string, index: number): string | undefined {
  if (!isLineStart(text, index))
    return undefined

  const line = text.slice(index).match(/^[ \t]{0,3}(`{3,}|~{3,})/)
  return line?.[1]
}

function findClosingFence(text: string, index: number, marker: string): number {
  const closingFence = new RegExp(`^[ \\t]{0,3}${marker[0]}{${marker.length},}[ \\t]*(?:\\n|$)`, 'm')
  const match = closingFence.exec(text.slice(index))
  return match ? index + match.index + match[0].length : -1
}

function findClosingDelimiter(text: string, index: number, delimiter: string): number {
  return text.indexOf(delimiter, index)
}

/**
 * remark-math recognizes dollar delimiters, while model output commonly uses
 * the TeX delimiters `\( ... \)` and `\[ ... \]`. Convert only complete
 * delimiters outside fenced and inline code so code examples stay untouched.
 */
export function normalizeLatexDelimiters(markdown: string): string {
  if (!markdown)
    return markdown

  let result = ''
  let index = 0

  while (index < markdown.length) {
    const fence = getFenceAt(markdown, index)
    if (fence) {
      const fenceEnd = findClosingFence(markdown, index + fence.length, fence)
      if (fenceEnd === -1)
        return result + markdown.slice(index)

      result += markdown.slice(index, fenceEnd)
      index = fenceEnd
      continue
    }

    if (markdown[index] === '`') {
      const codeDelimiter = markdown.slice(index).match(/^`+/)?.[0]
      if (codeDelimiter) {
        const codeEnd = markdown.indexOf(codeDelimiter, index + codeDelimiter.length)
        if (codeEnd === -1)
          return result + markdown.slice(index)

        const end = codeEnd + codeDelimiter.length
        result += markdown.slice(index, end)
        index = end
        continue
      }
    }

    if (markdown.startsWith('\\[', index)) {
      const mathEnd = findClosingDelimiter(markdown, index + 2, '\\]')
      if (mathEnd !== -1) {
        const math = markdown.slice(index + 2, mathEnd).trim()
        result += `\n\n$$\n${math}\n$$\n\n`
        index = mathEnd + 2
        continue
      }
    }

    if (markdown.startsWith('\\(', index)) {
      const mathEnd = findClosingDelimiter(markdown, index + 2, '\\)')
      if (mathEnd !== -1) {
        const math = markdown.slice(index + 2, mathEnd).trim()
        result += `$${math}$`
        index = mathEnd + 2
        continue
      }
    }

    result += markdown[index]
    index += 1
  }

  return result
}

export const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}

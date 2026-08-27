import type { CSSProperties, ReactNode } from 'react'
import type { Components, ExtraProps } from 'streamdown'

function parseInlineStyle(style: string): CSSProperties {
  const result: Record<string, string> = {}

  for (const declaration of style.split(';')) {
    const colonIndex = declaration.indexOf(':')
    if (colonIndex === -1)
      continue

    const property = declaration.slice(0, colonIndex).trim()
    const value = declaration.slice(colonIndex + 1).trim()
    if (!property || !value)
      continue

    const camelProperty = property.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase())
    result[camelProperty] = value
  }

  return result as CSSProperties
}

function getStyleFromNode(node?: ExtraProps['node']): CSSProperties | undefined {
  const rawStyle = node?.properties?.style
  if (typeof rawStyle !== 'string' || !rawStyle.trim())
    return undefined

  return parseInlineStyle(rawStyle)
}

interface KatexSpanProps extends ExtraProps {
  style?: CSSProperties
  children?: ReactNode
  className?: string
}

function KatexSpan({ node, style, children, className, ...props }: KatexSpanProps) {
  const katexStyle = getStyleFromNode(node)

  return (
    <span {...props} className={className} style={katexStyle ?? style}>
      {children}
    </span>
  )
}

export const katexStreamdownComponents: Components = {
  span: KatexSpan,
}

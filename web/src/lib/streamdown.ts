import { code } from '@streamdown/code'
import { createMathPlugin } from '@streamdown/math'

export const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}

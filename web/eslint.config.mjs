import antfu from '@antfu/eslint-config'

export default antfu(
  {
    react: true,
    typescript: true,
    formatters: true,
    ignores: ['dist', 'node_modules'],
  },
)

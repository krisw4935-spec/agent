import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { icons as lucideIcons } from '@iconify-json/lucide'
import { defineConfig, presetIcons, presetWind3 } from 'unocss'

const require = createRequire(import.meta.url)
const tailwindCompatReset = readFileSync(
  require.resolve('@unocss/reset/tailwind-compat.css'),
  'utf8',
)

export default defineConfig({
  content: {
    filesystem: [
      './src/**/*.{html,js,ts,jsx,tsx}',
      './node_modules/streamdown/dist/*.js',
      './node_modules/@streamdown/code/dist/*.js',
      './node_modules/@streamdown/math/dist/*.js',
    ],
    pipeline: {
      include: [
        /\.(vue|svelte|[jt]sx|mdx?|astro|elm|php|phtml|html)($|\?)/,
        /node_modules\/streamdown\/dist\/.*\.js$/,
        /node_modules\/@streamdown\/(?:code|math)\/dist\/.*\.js$/,
      ],
    },
  },
  outputToCssLayers: true,
  postprocess: (util) => {
    util.entries.forEach((entry) => {
      if (typeof entry[1] === 'string' && entry[1].includes(' in oklch'))
        entry[1] = entry[1].replaceAll(' in oklch', '')
    })
  },
  theme: {
    colors: {
      brand: '#0d7655',
      'brand-bg': '#e6f4ef',
      'brand-bg-hover': '#eff2fc',
      background: 'var(--background)',
      foreground: 'var(--foreground)',
      border: 'var(--border)',
      input: 'var(--input)',
      sidebar: 'var(--sidebar)',
      primary: {
        DEFAULT: 'var(--primary)',
        foreground: 'var(--primary-foreground)',
      },
      muted: {
        DEFAULT: 'var(--muted)',
        foreground: 'var(--muted-foreground)',
      },
      card: {
        DEFAULT: 'var(--card)',
        foreground: 'var(--card-foreground)',
      },
    },
  },
  shortcuts: {
    'bg-surface': 'bg-[var(--semi-color-bg-0)]',
    'bg-surface-2': 'bg-[var(--semi-color-bg-2)]',
    'border-default': 'border-[var(--semi-color-border)]',
    'text-brand': 'text-[rgb(var(--brand-primary))]',
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
  },
  preflights: [
    {
      layer: 'preflights',
      getCSS: () => tailwindCompatReset,
    },
  ],
  presets: [
    presetWind3(),
    presetIcons({
      scale: 1.2,
      extraProperties: {
        display: 'inline-block',
        verticalAlign: 'middle',
      },
      collections: {
        lucide: () => lucideIcons,
      },
    }),
  ],
})

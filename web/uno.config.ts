import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { defineConfig, presetWind3 } from 'unocss'

const require = createRequire(import.meta.url)
const tailwindCompatReset = readFileSync(
  require.resolve('@unocss/reset/tailwind-compat.css'),
  'utf8',
)

export default defineConfig({
  content: {
    filesystem: ['./src/**/*.{html,js,ts,jsx,tsx}'],
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
    },
  },
  preflights: [
    {
      layer: 'preflights',
      getCSS: () => tailwindCompatReset,
    },
  ],
  presets: [presetWind3()],
})

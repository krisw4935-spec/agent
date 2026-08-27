/// <reference types="@rsbuild/core/types" />

declare module 'virtual:uno.css' {
  const content: string
  export default content
}

declare module '*.css' {
  const content: string
  export default content
}

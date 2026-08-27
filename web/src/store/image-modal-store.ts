import { create } from 'zustand'

interface ImageModalState {
  openSrc: string | null
  open: (src: string) => void
  close: () => void
}

export const useImageModalStore = create<ImageModalState>((set) => ({
  openSrc: null,
  open(src) {
    set({ openSrc: src })
  },
  close() {
    set({ openSrc: null })
  },
}))

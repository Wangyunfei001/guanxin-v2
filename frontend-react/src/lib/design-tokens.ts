export const layoutTokens = {
  railWidth: 72,
  secondaryWidth: 264,
  inspectorWidth: 320,
  toolbarHeight: 56,
} as const

export const motionTokens = {
  instant: 0.12,
  component: 0.2,
  workflow: 0.28,
  page: 0.22,
  ease: [0.16, 1, 0.3, 1] as const,
} as const

export const zIndexTokens = {
  base: 0,
  sticky: 20,
  navigation: 30,
  overlay: 40,
  dialog: 50,
  toast: 60,
} as const

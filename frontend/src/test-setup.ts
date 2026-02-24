import '@testing-library/jest-dom/vitest'

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null
  readonly rootMargin = '0px'
  readonly thresholds = [0]

  disconnect(): void {}
  observe(): void {}
  takeRecords(): IntersectionObserverEntry[] { return [] }
  unobserve(): void {}
}

if (!globalThis.IntersectionObserver) {
  globalThis.IntersectionObserver = MockIntersectionObserver
}

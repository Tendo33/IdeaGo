import '@testing-library/jest-dom/vitest'
import { beforeAll } from 'vitest'
import i18n from "./i18n";

class MockIntersectionObserver implements IntersectionObserver {
	readonly root: Element | Document | null = null;
	readonly rootMargin = "0px";
	readonly thresholds = [0];

	disconnect(): void {}
	observe(): void {}
	takeRecords(): IntersectionObserverEntry[] {
		return [];
	}
	unobserve(): void {}
}

if (!globalThis.IntersectionObserver) {
	globalThis.IntersectionObserver = MockIntersectionObserver;
}

beforeAll(async () => {
	await i18n.changeLanguage("en");
});

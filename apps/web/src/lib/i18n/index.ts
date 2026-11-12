import { browser } from '$app/environment';
import { init, register, locale, waitLocale } from 'svelte-i18n';

const STORAGE_KEY = 'preferred-language';
export const SUPPORTED_LOCALES = ['en', 'fr'] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

register('en', () => import('./locales/en.json'));
register('fr', () => import('./locales/fr.json'));

export function setupI18n(initialLocale: string = 'en') {
	init({
		fallbackLocale: 'en',
		initialLocale
	});
}

export function setLocale(lang: SupportedLocale) {
	locale.set(lang);
	if (browser) localStorage.setItem(STORAGE_KEY, lang);
}

export function getSavedLocale(): SupportedLocale {
	if (!browser) return 'en';
	const saved = localStorage.getItem(STORAGE_KEY);
	return (SUPPORTED_LOCALES as readonly string[]).includes(saved ?? '')
		? (saved as SupportedLocale)
		: 'en';
}

/** Map language code to Intl locale string for date/number formatting. */
export function toIntlLocale(lang: string): string {
	return lang === 'fr' ? 'fr-FR' : 'en-US';
}

export { locale, waitLocale };

import { browser } from '$app/environment';
import { getSavedLocale, setupI18n, waitLocale } from '$lib/i18n';

export const load = async () => {
	setupI18n(browser ? getSavedLocale() : 'en');
	await waitLocale();
	return {};
};

import { get } from 'svelte/store';
import { locale } from 'svelte-i18n';

/** Derive the Intl locale string from the svelte-i18n locale store. */
function getIntlLocale(): string {
	const lang = get(locale) ?? 'en';
	return lang === 'fr' ? 'fr-FR' : 'en-US';
}

/**
 * Format a monetary amount according to currency rules.
 * XAF has no decimals; EUR and USD have 2.
 * Automatically uses the current app locale for number formatting.
 */
export function formatCurrency(amount: string | number, currency: string): string {
	const num = typeof amount === 'string' ? parseFloat(amount) : amount;
	if (isNaN(num)) return '–';

	const decimals = currency === 'XAF' ? 0 : 2;

	return new Intl.NumberFormat(getIntlLocale(), {
		style: 'currency',
		currency,
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals
	}).format(num);
}

export function formatDate(dateStr: string | null | undefined): string {
	if (!dateStr) return '–';
	try {
		return new Intl.DateTimeFormat(getIntlLocale(), {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric'
		}).format(new Date(dateStr));
	} catch {
		return dateStr;
	}
}

export function formatDateTime(dateStr: string | null | undefined): string {
	if (!dateStr) return '–';
	try {
		return new Intl.DateTimeFormat(getIntlLocale(), {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		}).format(new Date(dateStr));
	} catch {
		return dateStr;
	}
}

export function daysFromNow(dateStr: string | null | undefined): number | null {
	if (!dateStr) return null;
	const diff = new Date(dateStr).getTime() - Date.now();
	return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

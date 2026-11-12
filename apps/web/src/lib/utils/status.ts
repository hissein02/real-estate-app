import { get } from 'svelte/store';
import { t } from 'svelte-i18n';

export type BadgeVariant = 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'orange';

export const INVOICE_STATUS_COLORS: Record<string, BadgeVariant> = {
	issued: 'yellow',
	partially_paid: 'orange',
	paid: 'green',
	void: 'gray',
	draft: 'gray'
};

export const LEASE_STATUS_COLORS: Record<string, BadgeVariant> = {
	draft: 'gray',
	active: 'green',
	expired: 'yellow',
	terminated: 'red'
};

export const PAYMENT_STATUS_COLORS: Record<string, BadgeVariant> = {
	posted: 'green',
	void: 'gray'
};

/* The role name is the information. A colour per role adds none, and red on
   "admin" reads as an error rather than a privilege level. */
export const ROLE_COLORS: Record<string, BadgeVariant> = {
	admin: 'gray',
	manager: 'gray',
	accountant: 'gray',
	agent: 'gray',
	read_only: 'gray'
};

/** Returns translated invoice status label using the current locale. */
export function getInvoiceStatusLabel(status: string): string {
	const T = get(t);
	const key = `status.invoice.${status}`;
	const translated = T(key);
	// Fall back to capitalized status if key not found
	return translated && translated !== key ? translated : status;
}

/** Returns translated lease status label using the current locale. */
export function getLeaseStatusLabel(status: string): string {
	const T = get(t);
	const key = `status.lease.${status}`;
	const translated = T(key);
	return translated && translated !== key ? translated : status;
}

/** Returns translated role label using the current locale. */
export function getRoleLabel(role: string): string {
	const T = get(t);
	const key = `status.role.${role}`;
	const translated = T(key);
	return translated && translated !== key ? translated : role;
}

/** Returns translated deposit status label using the current locale. */
export function getDepositStatusLabel(status: string): string {
	const T = get(t);
	const key = `status.deposit.${status}`;
	const translated = T(key);
	return translated && translated !== key ? translated : status;
}

/** Returns translated notification status label using the current locale. */
export function getNotificationStatusLabel(status: string): string {
	const T = get(t);
	const key = `status.notification.${status}`;
	const translated = T(key);
	return translated && translated !== key ? translated : status;
}

// Legacy static label maps — kept for backward compatibility.
// Prefer using the getXxxStatusLabel() functions or $t('status.xxx') directly in templates.
export const INVOICE_STATUS_LABELS: Record<string, string> = {
	issued: 'Issued',
	partially_paid: 'Partial',
	paid: 'Paid',
	void: 'Void',
	draft: 'Draft'
};

export const LEASE_STATUS_LABELS: Record<string, string> = {
	draft: 'Draft',
	active: 'Active',
	expired: 'Expired',
	terminated: 'Terminated'
};

export const ROLE_LABELS: Record<string, string> = {
	admin: 'Admin',
	manager: 'Manager',
	accountant: 'Accountant',
	agent: 'Agent',
	read_only: 'Read Only'
};

export const VARIANT_CLASSES: Record<BadgeVariant, string> = {
	green: 'bg-green-100 text-green-800',
	red: 'bg-red-100 text-red-800',
	yellow: 'bg-yellow-100 text-yellow-800',
	blue: 'bg-blue-100 text-blue-800',
	gray: 'bg-gray-100 text-gray-600',
	orange: 'bg-orange-100 text-orange-800'
};

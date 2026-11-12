import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import type { PaginatedResponse } from './types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const SESSION_EXPIRY_KEY = 'session_expires_at';
const REMEMBER_ME_DURATION_MS = 12 * 60 * 60 * 1000; // 12 hours

function getAccessToken(): string | null {
	if (!browser) return null;
	return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
}

function getRefreshToken(): string | null {
	if (!browser) return null;
	return localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');
}

function setTokens(access: string, refresh?: string, rememberMe = false) {
	const storage = rememberMe ? localStorage : sessionStorage;
	storage.setItem('access_token', access);
	if (refresh) storage.setItem('refresh_token', refresh);
	if (rememberMe) {
		localStorage.setItem(SESSION_EXPIRY_KEY, String(Date.now() + REMEMBER_ME_DURATION_MS));
	}
}

function clearTokens() {
	localStorage.removeItem('access_token');
	localStorage.removeItem('refresh_token');
	localStorage.removeItem(SESSION_EXPIRY_KEY);
	sessionStorage.removeItem('access_token');
	sessionStorage.removeItem('refresh_token');
}

function isSessionExpired(): boolean {
	const expiry = localStorage.getItem(SESSION_EXPIRY_KEY);
	if (!expiry) return false;
	return Date.now() > parseInt(expiry);
}

async function refreshAccessToken(): Promise<string | null> {
	if (isSessionExpired()) {
		clearTokens();
		return null;
	}
	const refresh = getRefreshToken();
	if (!refresh) return null;

	const res = await fetch(`${API_BASE}/api/v1/auth/token/refresh/`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ refresh })
	});

	if (!res.ok) {
		clearTokens();
		return null;
	}

	const data = await res.json();
	// Preserve the original storage: if token was in localStorage, keep rememberMe=true
	const wasRemembered = browser && !!localStorage.getItem('refresh_token');
	setTokens(data.access, data.refresh, wasRemembered);
	return data.access;
}

async function apiFetch<T = unknown>(
	path: string,
	options: RequestInit = {},
	retry = true
): Promise<T> {
	const url = path.startsWith('http') ? path : `${API_BASE}/api/v1${path}`;
	const token = getAccessToken();

	const headers: Record<string, string> = {
		...(options.body && !(options.body instanceof FormData)
			? { 'Content-Type': 'application/json' }
			: {}),
		...(token ? { Authorization: `Bearer ${token}` } : {}),
		...(options.headers as Record<string, string> | undefined)
	};

	const res = await fetch(url, { ...options, headers });

	if (res.status === 401 && retry) {
		const newToken = await refreshAccessToken();
		if (newToken) {
			return apiFetch<T>(path, options, false);
		}
		clearTokens();
		if (browser) goto('/login');
		throw new Error('Session expired');
	}

	if (!res.ok) {
		let errorData: unknown;
		try {
			errorData = await res.json();
		} catch {
			errorData = { detail: res.statusText };
		}
		const err = new Error(
			typeof errorData === 'object' && errorData !== null && 'detail' in errorData
				? String((errorData as { detail: unknown }).detail)
				: `HTTP ${res.status}`
		);
		(err as { data?: unknown }).data = errorData;
		throw err;
	}

	if (res.status === 204) return undefined as T;

	return res.json() as Promise<T>;
}

export const api = {
	// Public - no auth required
	branding: () =>
		apiFetch<{ display_name: string; logo_url: string | null }>('/branding/'),

	// Auth
	login: (username: string, password: string, rememberMe = false) =>
		apiFetch<{ access: string; refresh: string }>('/auth/login/', {
			method: 'POST',
			body: JSON.stringify({ username, password })
		}).then((data) => {
			setTokens(data.access, data.refresh, rememberMe);
			return data;
		}),

	logout: () => {
		const refresh = getRefreshToken();
		return apiFetch('/auth/logout/', {
			method: 'POST',
			body: JSON.stringify({ refresh })
		}).finally(clearTokens);
	},

	me: () => apiFetch<import('./types').User>('/auth/me/'),

	// Users (admin)
	users: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').User>>(`/users/?${params}`),
		get: (id: number) => apiFetch<import('./types').User>(`/users/${id}/`),
		create: (data: import('./types').UserCreatePayload) =>
			apiFetch<import('./types').User>('/users/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: import('./types').UserUpdatePayload) =>
			apiFetch<import('./types').User>(`/users/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/users/${id}/`, { method: 'DELETE' }),
		setPassword: (id: number, newPassword: string) =>
			apiFetch<{ detail: string }>(`/users/${id}/set-password/`, {
				method: 'POST',
				body: JSON.stringify({ new_password: newPassword })
			})
	},

	// Owners
	owners: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Owner>>(`/owners/?${params}`),
		get: (id: number) => apiFetch<import('./types').Owner>(`/owners/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Owner>('/owners/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: unknown) =>
			apiFetch<import('./types').Owner>(`/owners/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/owners/${id}/`, { method: 'DELETE' })
	},

	// Properties
	properties: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Property>>(`/properties/?${params}`),
		get: (id: number) => apiFetch<import('./types').Property>(`/properties/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Property>('/properties/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: unknown) =>
			apiFetch<import('./types').Property>(`/properties/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/properties/${id}/`, { method: 'DELETE' })
	},

	// Units
	units: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Unit>>(`/units/?${params}`),
		get: (id: number) => apiFetch<import('./types').Unit>(`/units/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Unit>('/units/', { method: 'POST', body: JSON.stringify(data) }),
		update: (id: number, data: unknown) =>
			apiFetch<import('./types').Unit>(`/units/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/units/${id}/`, { method: 'DELETE' })
	},

	// Tenants
	tenants: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Tenant>>(`/tenants/?${params}`),
		get: (id: number) => apiFetch<import('./types').Tenant>(`/tenants/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Tenant>('/tenants/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: unknown) =>
			apiFetch<import('./types').Tenant>(`/tenants/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/tenants/${id}/`, { method: 'DELETE' })
	},

	// Leases
	leases: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Lease>>(`/leases/?${params}`),
		get: (id: number) => apiFetch<import('./types').Lease>(`/leases/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Lease>('/leases/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: unknown) =>
			apiFetch<import('./types').Lease>(`/leases/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		activate: (id: number) =>
			apiFetch<import('./types').Lease>(`/leases/${id}/activate/`, { method: 'POST' }),
		terminate: (id: number, data: unknown) =>
			apiFetch<import('./types').Lease>(`/leases/${id}/terminate/`, {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		renew: (id: number, data: unknown) =>
			apiFetch<import('./types').Lease>(`/leases/${id}/renew/`, {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		delete: (id: number) => apiFetch(`/leases/${id}/`, { method: 'DELETE' }),
		deletionPreview: (id: number) =>
			apiFetch<{ lease_repr: string; will_delete: Record<string, number>; total: number }>(
				`/leases/${id}/deletion-preview/`
			),
		forceDelete: (id: number, reason = '') =>
			apiFetch(`/leases/${id}/force-delete/`, {
				method: 'DELETE',
				body: JSON.stringify({ confirm: true, reason })
			})
	},

	// Invoices
	invoices: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Invoice>>(`/invoices/?${params}`),
		get: (id: number) => apiFetch<import('./types').InvoiceDetail>(`/invoices/${id}/`),
		preview: (id: number) =>
			apiFetch<{ html: string; invoice_number: string }>(`/invoices/${id}/preview/`),
		emailPreview: (id: number) =>
			apiFetch<{ subject: string; body: string; default_recipient: string }>(
				`/invoices/${id}/email-preview/`
			),
		send: (id: number, data: { recipients: string[]; subject?: string; body?: string }) =>
			apiFetch<{ sent: string[]; failed: string[] }>(`/invoices/${id}/send/`, {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		setDates: (id: number, data: { invoice_date?: string; due_date?: string; reason?: string }) =>
			apiFetch<import('./types').Invoice & { warnings: string[] }>(`/invoices/${id}/dates/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		void: (id: number, reason: string) =>
			apiFetch<import('./types').Invoice>(`/invoices/${id}/void/`, {
				method: 'POST',
				body: JSON.stringify({ reason })
			}),
		generate: (data: import('./types').InvoiceGeneratePayload) =>
			apiFetch<import('./types').InvoiceDetail>('/invoices/generate/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		/** Returns the absolute URL for the server-rendered PDF (WeasyPrint). */
		pdfUrl: (id: number) => `${API_BASE}/api/v1/invoices/${id}/pdf/`
	},

	// Payments
	payments: {
		list: (params = '') =>
			apiFetch<PaginatedResponse<import('./types').Payment>>(`/payments/?${params}`),
		get: (id: number) => apiFetch<import('./types').Payment>(`/payments/${id}/`),
		create: (data: unknown) =>
			apiFetch<import('./types').Payment>('/payments/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		allocate: (data: unknown) =>
			apiFetch('/payments/allocate/', { method: 'POST', body: JSON.stringify(data) }),
		void: (id: number, reason: string) =>
			apiFetch<import('./types').Payment>(`/payments/${id}/void/`, {
				method: 'POST',
				body: JSON.stringify({ reason })
			})
	},

	// Deposits
	deposits: {
		list: (params = '') => apiFetch(`/deposits/?${params}`),
		balance: (leaseId: number) => apiFetch(`/deposits/balance/?lease_id=${leaseId}`),
		receive: (data: unknown) =>
			apiFetch('/deposits/receive/', { method: 'POST', body: JSON.stringify(data) }),
		refund: (data: unknown) =>
			apiFetch('/deposits/refund/', { method: 'POST', body: JSON.stringify(data) })
	},

	// Reports
	reports: {
		dashboard: () => apiFetch<import('./types').DashboardKPI>('/reports/dashboard/'),
		arrears: () =>
			apiFetch<{
				items: import('./types').ArrearsItem[];
				total_overdue_amount: string;
				overdue_invoice_count: number;
			}>('/reports/arrears/'),
		schedule: (params = '') =>
			apiFetch<import('./types').PaymentSchedule>(`/reports/payment-schedule/?${params}`),
		exportInvoices: (fmt: 'csv' | 'xlsx' = 'csv') =>
			`${API_BASE}/api/v1/reports/export/invoices/?fmt=${fmt}`,
		exportPayments: (fmt: 'csv' | 'xlsx' = 'csv') =>
			`${API_BASE}/api/v1/reports/export/payments/?fmt=${fmt}`
	},

	// Audit
	auditLogs: {
		list: (params = '') => apiFetch(`/audit-logs/?${params}`)
	},

	// Settings (admin)
	settings: {
		getTasks: () => apiFetch<import('./types').TaskConfig[]>('/settings/tasks/'),
		updateTask: (taskKey: string, data: Partial<Pick<import('./types').TaskConfig, 'is_enabled' | 'hour' | 'minute'>>) =>
			apiFetch<import('./types').TaskConfig>(`/settings/tasks/${taskKey}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		getEmail: () => apiFetch<import('./types').EmailSettingsData>('/settings/email/'),
		updateEmail: (data: Partial<import('./types').EmailSettingsData>) =>
			apiFetch<import('./types').EmailSettingsData>('/settings/email/', {
				method: 'PUT',
				body: JSON.stringify(data)
			}),
		getTemplate: (type: string) =>
			apiFetch<import('./types').NotificationTemplateData>(`/settings/email-templates/${type}/`),
		updateTemplate: (type: string, data: { subject_template?: string; body_template?: string }) =>
			apiFetch<import('./types').NotificationTemplateData>(`/settings/email-templates/${type}/`, {
				method: 'PUT',
				body: JSON.stringify(data)
			}),
		sendTestEmail: (type: string, recipientEmail: string) =>
			apiFetch<{ detail: string }>(`/settings/email-templates/${type}/send-test/`, {
				method: 'POST',
				body: JSON.stringify({ recipient_email: recipientEmail })
			}),
		getCompany: () => apiFetch<import('./types').CompanyInfoData>('/settings/company/'),
		updateCompany: (data: Partial<import('./types').CompanyInfoData> & { pdf_signatory_id?: number | null }) =>
			apiFetch<import('./types').CompanyInfoData>('/settings/company/', {
				method: 'PUT',
				body: JSON.stringify(data)
			}),
		uploadLogo: (file: File) => {
			const formData = new FormData();
			formData.append('logo', file);
			return apiFetch<import('./types').CompanyInfoData>('/settings/company/logo/', {
				method: 'POST',
				body: formData
			});
		},
		deleteLogo: () =>
			apiFetch<import('./types').CompanyInfoData>('/settings/company/logo/', {
				method: 'DELETE'
			}),
		getInvoiceEmailPreview: () =>
			apiFetch<{ html: string }>('/settings/invoice-email/preview/'),
		sendTestInvoiceEmail: (recipientEmail: string) =>
			apiFetch<{ detail: string }>('/settings/invoice-email/send-test/', {
				method: 'POST',
				body: JSON.stringify({
					recipient_email: recipientEmail
				})
			})
	},

	notifications: {
		list: (params?: string) =>
			apiFetch<import('./types').PaginatedResponse<import('./types').NotificationData>>(
				`/notifications/${params ? `?${params}` : ''}`
			)
	},

	// Signatories
	signatories: {
		list: () => apiFetch<import('./types').Signatory[]>('/settings/signatories/'),
		create: (data: { label: string; name?: string; order?: number }) =>
			apiFetch<import('./types').Signatory>('/settings/signatories/', {
				method: 'POST',
				body: JSON.stringify(data)
			}),
		update: (id: number, data: { label?: string; name?: string; order?: number }) =>
			apiFetch<import('./types').Signatory>(`/settings/signatories/${id}/`, {
				method: 'PATCH',
				body: JSON.stringify(data)
			}),
		remove: (id: number) => apiFetch(`/settings/signatories/${id}/`, { method: 'DELETE' }),
		uploadSignature: (id: number, file: File) => {
			const formData = new FormData();
			formData.append('signature', file);
			return apiFetch<import('./types').Signatory>(`/settings/signatories/${id}/signature/`, {
				method: 'POST',
				body: formData
			});
		},
		deleteSignature: (id: number) =>
			apiFetch<import('./types').Signatory>(`/settings/signatories/${id}/signature/`, {
				method: 'DELETE'
			})
	}
};

/**
 * Download a protected file.
 *
 * A plain `<a href>` sends no Authorization header — the JWT lives in storage,
 * not in a cookie — so linking straight to an API endpoint returns 401. Fetch
 * it with the token, then hand the browser a blob.
 */
export async function downloadWithAuth(url: string, fallbackName: string): Promise<void> {
	const token = getAccessToken();
	const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
	if (!res.ok) {
		let detail = `HTTP ${res.status}`;
		try {
			detail = (await res.json()).detail ?? detail;
		} catch {
			/* non-JSON error body */
		}
		throw new Error(detail);
	}

	// Prefer the filename the server chose.
	let name = fallbackName;
	const disposition = res.headers.get('Content-Disposition') ?? '';
	const match = disposition.match(/filename="?([^";]+)"?/);
	if (match) name = match[1];

	const objectUrl = URL.createObjectURL(await res.blob());
	const a = document.createElement('a');
	a.href = objectUrl;
	a.download = name;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(objectUrl);
}

export function mediaUrl(path: string | null): string | null {
	if (!path) return null;
	return path.startsWith('http') ? path : `${API_BASE}${path}`;
}

export { setTokens, clearTokens, getAccessToken, API_BASE };

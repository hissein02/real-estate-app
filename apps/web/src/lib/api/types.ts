export interface User {
	id: number;
	username: string;
	email: string;
	first_name: string;
	last_name: string;
	role: 'admin' | 'manager' | 'accountant' | 'agent' | 'read_only';
	is_active: boolean;
	date_joined: string;
}

export interface PaginatedResponse<T> {
	count: number;
	next: string | null;
	previous: string | null;
	results: T[];
}

export interface Owner {
	id: number;
	first_name: string;
	last_name: string;
	company_name: string;
	is_company: boolean;
	email: string;
	phone: string;
	address: string;
	notes?: string;
	display_name: string;
	created_at: string;
}

export interface Property {
	id: number;
	name: string;
	property_type: string;
	owner: number;
	owner_name: string;
	address_line1: string;
	address_line2?: string;
	city: string;
	country: string;
	postal_code?: string;
	description?: string;
	full_address: string;
	unit_count: number;
	units?: Unit[];
	created_at: string;
}

export interface Unit {
	id: number;
	building: number;
	property_name: string;
	name: string;
	unit_type: string;
	floor: number | null;
	surface_area: string | null;
	description?: string;
	is_active: boolean;
	is_occupied: boolean;
	created_at: string;
}

export interface Tenant {
	id: number;
	first_name: string;
	last_name: string;
	company_name: string;
	is_company: boolean;
	email: string;
	phone: string;
	id_number?: string;
	address?: string;
	notes?: string;
	display_name: string;
	created_at: string;
}

export interface Lease {
	id: number;
	unit: number;
	unit_name: string;
	tenant: number;
	tenant_name: string;
	status: 'draft' | 'active' | 'expired' | 'terminated';
	start_date: string;
	end_date: string | null;
	rent_unit_price: string;
	rent_period_total: string;
	currency: 'XAF' | 'EUR' | 'USD';
	billing_interval_months: number;
	billing_cycle_anchor: 'lease_start' | 'month_start';
	prorate_first_period: boolean;
	deposit_amount: string;
	late_fee_type: 'none' | 'fixed' | 'percentage';
	late_fee_value: string;
	late_fee_grace_period_days: number;
	monthly_rent_equivalent: string;
	notes?: string;
	created_at: string;
}

export interface Invoice {
	id: number;
	lease: number;
	tenant_name: string;
	unit_name: string;
	invoice_number: string;
	period_start: string;
	period_end: string;
	invoice_date: string | null;
	due_date: string;
	currency: string;
	total_amount: string;
	paid_amount: string;
	balance: string;
	status: 'draft' | 'issued' | 'partially_paid' | 'paid' | 'void';
	is_prorated: boolean;
	is_overdue: boolean;
	notes: string;
	created_at: string;
}

export interface Payment {
	id: number;
	lease: number;
	tenant_name: string;
	amount: string;
	currency: string;
	payment_date: string;
	payment_method: string;
	reference: string;
	status: 'posted' | 'void';
	unallocated_amount: string;
	created_at: string;
}

export interface RevenueTrendPoint {
	month: string;
	amount: string;
}

export interface YearTrendPoint {
	month: string;    // "2026-01"
	expected: string; // total invoiced amount
	actual: string;   // paid amount
}

export interface MonthTenant {
	tenant: string;
	unit: string;
	property: string;
	amount: string;
	paid: string;
	balance: string;
	status: string;
	is_overdue: boolean;
	due_date: string;
	invoice_number: string;
	currency: string;
}

export interface PaymentMethodBreakdown {
	method: string;
	amount: string;
	count: number;
}

export interface TopProperty {
	name: string;
	revenue: string;
	total_units: number;
	occupied_units: number;
}

export interface DashboardKPI {
	active_leases: number;
	expiring_30d: number;
	overdue_invoice_count: number;
	total_overdue_amount: string;
	monthly_collected: string;  // actual paid amount this month
	monthly_invoiced: string;   // total invoiced this month
	monthly_expected: string;   // theoretical from active leases
	collection_rate: number;
	total_units: number;
	occupied_units: number;
	occupancy_rate: number;
	tenant_count: number;
	property_count: number;
	revenue_trend: RevenueTrendPoint[];
	year_trend: YearTrendPoint[];
	month_tenants: MonthTenant[];
	payment_methods: PaymentMethodBreakdown[];
	invoice_statuses: {
		draft: number;
		issued: number;
		partially_paid: number;
		paid: number;
		overdue: number;
	};
	top_properties: TopProperty[];
}

export interface ArrearsItem {
	invoice_number: string;
	tenant: string;
	unit: string;
	due_date: string;
	days_overdue: number;
	total_amount: string;
	paid_amount: string;
	balance: string;
	currency: string;
}

// Payment Schedule types
export type PeriodStatus = 'paid' | 'partially_paid' | 'overdue' | 'issued' | 'future' | 'void' | 'no_lease';

export interface SchedulePeriod {
	month: string;
	status: PeriodStatus;
	amount: string | null;
	paid: string | null;
	invoice_id: number | null;
	is_prorated: boolean;
	period_start: string | null;
	period_end: string | null;
}

export interface ScheduleUnit {
	unit_id: number;
	unit_name: string;
	tenant_name: string;
	tenant_email: string;
	rent_unit_price: string;
	rent_period_total: string;
	currency: string;
	billing_interval_months: number;
	lease_id: number;
	periods: SchedulePeriod[];
}

export interface ScheduleProperty {
	id: number;
	name: string;
	units: ScheduleUnit[];
}

export interface ScheduleSummary {
	total_expected: string;
	total_paid: string;
	total_overdue: string;
	total_upcoming: string;
}

export interface PaymentSchedule {
	months: string[];
	properties: ScheduleProperty[];
	summary: ScheduleSummary;
}

// Invoice detail types (for generate endpoint)
export interface InvoiceLine {
	id: number;
	line_type: 'rent' | 'deposit' | 'late_fee' | 'adjustment' | 'other';
	description: string;
	quantity: string;
	unit_price: string;
	amount: string;
}

export interface InvoiceDetail extends Invoice {
	lines: InvoiceLine[];
	proration_details: Record<string, string> | null;
}

export interface InvoiceLineInput {
	line_type: 'adjustment' | 'other';
	description: string;
	quantity: number;
	unit_price: number;
}

export interface PdfOverrides {
	pdf_show_rccm?: boolean;
	pdf_show_nif?: boolean;
	pdf_bank_display?: 'none' | 'all' | 'selected';
	pdf_selected_bank_indices?: number[];
	pdf_signatory_id?: number | null;
}

export interface InvoiceGeneratePayload {
	lease_id: number;
	period_start: string;
	/** Blank or omitted: the API assigns the next number in the sequence. */
	invoice_number?: string;
	invoice_date?: string;
	extra_lines?: InvoiceLineInput[];
	notes?: string;
	pdf_overrides?: PdfOverrides;
}

// ── Settings ──
export interface TaskConfig {
	task_key: string;
	task_name: string;
	description: string;
	is_enabled: boolean;
	hour: number;
	minute: number;
	periodicity: string;
}

export interface EmailSettingsData {
	smtp_host: string;
	smtp_port: number;
	smtp_use_tls: boolean;
	smtp_username: string;
	smtp_password: string;
	from_name: string;
	from_email: string;
	reply_to_email: string;
	task_timezone: string;
}

export interface NotificationTemplateData {
	notification_type: string;
	subject_template: string;
	body_template: string;
	available_variables: string[];
	sample_data: Record<string, string>;
}

// ── User Management ──
export interface UserCreatePayload {
	username: string;
	email: string;
	first_name: string;
	last_name: string;
	role: User['role'];
	password: string;
}

export interface UserUpdatePayload {
	username?: string;
	email?: string;
	first_name?: string;
	last_name?: string;
	role?: User['role'];
	is_active?: boolean;
}

// ── Company Info ──
export interface BankAccount {
	bank_name: string;
	account_number: string;
}

export interface Signatory {
	id: number;
	label: string;
	name: string;
	signature_url: string | null;
	order: number;
}

export type NotificationType =
	| 'rent_reminder'
	| 'overdue_notice'
	| 'lease_expiry_warning'
	| 'invoice_generated'
	| 'payment_received';

export type NotificationStatus = 'pending' | 'sent' | 'failed';

export interface NotificationLeaseInfo {
	id: number;
	tenant_name: string;
	unit_name: string;
}

export interface NotificationData {
	id: number;
	lease: number | null;
	lease_info: NotificationLeaseInfo | null;
	notification_type: NotificationType;
	type_display: string;
	recipient_email: string;
	subject: string;
	content: string;
	body: string;
	triggered_by: string;
	status: NotificationStatus;
	status_display: string;
	sent_at: string | null;
	error_message: string;
	created_at: string;
}

export interface CompanyInfoData {
	display_name: string;
	company_name: string;
	address: string;
	city: string;
	country: string;
	phone_numbers: string[];
	email: string;
	logo_url: string | null;
	bank_accounts: BankAccount[];
	rccm: string;
	nif: string;
	// PDF display preferences
	pdf_show_rccm: boolean;
	pdf_show_nif: boolean;
	pdf_bank_display: 'none' | 'all' | 'selected';
	pdf_selected_bank_indices: number[];
	pdf_signatory: Signatory | null;
}

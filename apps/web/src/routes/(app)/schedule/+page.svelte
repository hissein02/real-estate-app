<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { api, getAccessToken, mediaUrl } from '$lib/api/client';
	import RichTextEditor from '$lib/components/RichTextEditor.svelte';
	import type {
		PaymentSchedule,
		ScheduleProperty,
		ScheduleUnit,
		SchedulePeriod,
		PeriodStatus,
		Property,
		InvoiceDetail,
		InvoiceLineInput,
		Signatory
	} from '$lib/api/types';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import Spinner from '$lib/components/Spinner.svelte';
	import InvoicePreview from '$lib/components/InvoicePreview.svelte';
	import { companyInfo } from '$lib/stores/auth';

	let schedule: PaymentSchedule | null = null;
	let loading = true;
	let error = '';

	// Controls
	const _now = new Date();
	let viewType: '6m' | '12m' = '6m';
	let periodYear: number = _now.getFullYear();
	let periodHalf: 1 | 2 = _now.getMonth() < 6 ? 1 : 2;
	let propertyFilter = '';
	let viewMode: 'grid' | 'cards' = 'grid';
	let propertyOptions: Property[] = [];

	$: ownerByPropertyId = Object.fromEntries(propertyOptions.map(p => [p.id, p.owner_name]));

	// Collapsed state for property groups (cards view)
	let collapsed: Record<number, boolean> = {};

	// Computed period months list (always 6 or 12 fixed calendar months)
	$: periodMonths = (() => {
		const months: string[] = [];
		const startM = viewType === '12m' ? 1 : (periodHalf === 1 ? 1 : 7);
		const endM   = viewType === '12m' ? 12 : (periodHalf === 1 ? 6 : 12);
		for (let m = startM; m <= endM; m++) {
			months.push(`${periodYear}-${String(m).padStart(2, '0')}`);
		}
		return months;
	})();

	$: periodLabel = (() => {
		if (viewType === '12m') return String(periodYear);
		return periodHalf === 1 ? `Jan – Jun ${periodYear}` : `Jul – Dec ${periodYear}`;
	})();

	// ── Unified Slide-over Panel ──
	let panelOpen = false;
	let panelStep: 'details' | 'form' | 'preview' | 'success' | 'send' = 'details';
	let selectedPeriod: SchedulePeriod | null = null;
	let selectedUnit: ScheduleUnit | null = null;
	let selectedProperty: ScheduleProperty | null = null;
	let existingInvoice: InvoiceDetail | null = null;
	let loadingInvoice = false;

	// Invoice generation state
	let generatedInvoice: (InvoiceDetail & { email_sent?: boolean }) | null = null;
	let generatorLoading = false;
	let panelError = '';
	let pdfLoading = false;

	// Extra lines for invoice
	let extraLines: { line_type: 'adjustment' | 'other'; description: string; quantity: number; unit_price: number }[] = [];
	let invoiceNotes = '';
	// Sending is its own step, reached from an invoice that already exists.
	let recipients: string[] = [];
	let sending = false;
	let loadingDraft = false;
	let sendSubject = '';
	let sendBody = '';
	let sendResult: { sent: string[]; failed: string[] } | null = null;
	let invoiceDate = new Date().toISOString().slice(0, 10);
	// Blank = the API assigns the next number in the month's sequence.
	let invoiceNumber = '';

	// ── Per-invoice PDF overrides (initialized from company defaults) ──
	let ovShowRccm = true;
	let ovShowNif = true;
	let ovBankDisplay: 'none' | 'all' | 'selected' = 'all';
	let ovSelectedBankIndices: number[] = [];
	let ovSignatory: number | null = null;
	let pdfOptionsExpanded = false;

	// Signatories list loaded from API
	let signatories: Signatory[] = [];

	function resetPdfOverrides() {
		ovShowRccm = $companyInfo?.pdf_show_rccm ?? true;
		ovShowNif = $companyInfo?.pdf_show_nif ?? true;
		ovBankDisplay = $companyInfo?.pdf_bank_display ?? 'all';
		ovSelectedBankIndices = [...($companyInfo?.pdf_selected_bank_indices ?? [])];
		ovSignatory = $companyInfo?.pdf_signatory?.id ?? null;
		pdfOptionsExpanded = false;
	}

	function toggleOvBankIndex(index: number) {
		if (ovSelectedBankIndices.includes(index)) {
			ovSelectedBankIndices = ovSelectedBankIndices.filter(i => i !== index);
		} else {
			ovSelectedBankIndices = [...ovSelectedBankIndices, index];
		}
	}

	// Computed: signatory object for the selected signatory ID
	$: ovSignatoryPreview = signatories.find(s => s.id === ovSignatory);

	// Computed: signature image URL for the selected signatory (null if unavailable)
	$: ovSignatureImageUrl = ovSignatoryPreview?.signature_url
		? mediaUrl(ovSignatoryPreview.signature_url)
		: null;

	async function load() {
		loading = true;
		error = '';
		try {
			const today = new Date();
			const todayYear = today.getFullYear();
			const todayMonth = today.getMonth() + 1; // 1-12
			const startM = viewType === '12m' ? 1 : (periodHalf === 1 ? 1 : 7);
			const endM   = viewType === '12m' ? 12 : (periodHalf === 1 ? 6 : 12);
			const monthsBack = Math.max(0, (todayYear - periodYear) * 12 + (todayMonth - startM));
			const monthsAhead = Math.max(0, (periodYear - todayYear) * 12 + (endM - todayMonth) + 1);
			const params = new URLSearchParams({
				months: String(monthsAhead),
				months_back: String(monthsBack)
			});
			if (propertyFilter) params.set('property', propertyFilter);
			const res = await api.reports.schedule(params.toString());
			schedule = res;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error loading schedule';
		} finally {
			loading = false;
		}
	}

	async function loadProperties() {
		try {
			const res = await api.properties.list('page_size=1000');
			propertyOptions = res.results;
		} catch {}
	}

	async function loadSignatories() {
		try {
			signatories = await api.signatories.list();
		} catch {}
	}

	onMount(() => {
		load();
		loadProperties();
		loadSignatories();
	});

	function navigatePrev() {
		if (viewType === '12m') {
			periodYear -= 1;
		} else {
			if (periodHalf === 1) { periodYear -= 1; periodHalf = 2; }
			else { periodHalf = 1; }
		}
		load();
	}

	function navigateNext() {
		if (viewType === '12m') {
			periodYear += 1;
		} else {
			if (periodHalf === 2) { periodYear += 1; periodHalf = 1; }
			else { periodHalf = 2; }
		}
		load();
	}

	function formatMonth(monthStr: string): string {
		const [year, month] = monthStr.split('-');
		const date = new Date(Number(year), Number(month) - 1);
		return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
	}

	function formatMonthShort(monthStr: string): string {
		const [year, month] = monthStr.split('-');
		const date = new Date(Number(year), Number(month) - 1);
		return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
	}

	function isCurrentMonth(monthStr: string): boolean {
		const now = new Date();
		const current = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
		return monthStr === current;
	}

	// Status styling
	const statusConfig: Record<PeriodStatus, { bg: string; color: string; dotColor: string; border: string }> = {
		paid:           { bg: '#dcfce7', color: '#166534', dotColor: '#16a34a', border: '#86efac' },
		partially_paid: { bg: '#fff7ed', color: '#9a3412', dotColor: '#ea580c', border: '#fdba74' },
		overdue:        { bg: '#fee2e2', color: '#991b1b', dotColor: '#dc2626', border: '#fca5a5' },
		issued:         { bg: '#fefce8', color: '#854d0e', dotColor: '#ca8a04', border: '#fde047' },
		future:         { bg: '#f8fafc', color: '#64748b', dotColor: '#94a3b8', border: '#e2e8f0' },
		void:           { bg: '#f9fafb', color: '#9ca3af', dotColor: '#d1d5db', border: '#e5e7eb' },
		no_lease:       { bg: 'transparent', color: '#d1d5db', dotColor: '#e5e7eb', border: 'transparent' }
	};

	function getPeriodStatusLabel(status: string): string {
		const T = get(t);
		const key = `status.periodStatus.${status}`;
		return T(key) || status;
	}

	function getPeriodForMonth(periods: SchedulePeriod[], month: string): SchedulePeriod | undefined {
		return periods.find((p) => p.month === month);
	}

	function formatCompact(amount: string | null, _currency: string): string {
		if (!amount) return '';
		const num = parseFloat(amount);
		if (isNaN(num)) return '';
		if (num >= 1_000_000) return `${parseFloat((num / 1_000_000).toFixed(1))}M`;
		if (num >= 1_000)     return `${parseFloat((num / 1_000).toFixed(1))}k`;
		return String(Math.round(num));
	}

	function toggleCollapse(propId: number) {
		collapsed[propId] = !collapsed[propId];
	}

	// ── Panel logic ──
	async function openPanel(period: SchedulePeriod, unit: ScheduleUnit, prop: ScheduleProperty) {
		if (period.status === 'no_lease') return;
		selectedPeriod = period;
		selectedUnit = unit;
		selectedProperty = prop;
		existingInvoice = null;
		generatedInvoice = null;
		panelError = '';
		panelStep = 'details';
		panelOpen = true;
		extraLines = [];
		invoiceNumber = '';
		invoiceNotes = '';
		resetPdfOverrides();

		if (period.invoice_id) {
			loadingInvoice = true;
			try {
				existingInvoice = await api.invoices.get(period.invoice_id);
			} catch {
				existingInvoice = null;
			} finally {
				loadingInvoice = false;
			}
		}
	}

	function closePanel() {
		panelOpen = false;
		panelStep = 'details';
		selectedPeriod = null;
		selectedUnit = null;
		selectedProperty = null;
		existingInvoice = null;
		generatedInvoice = null;
		extraLines = [];
		invoiceNumber = '';
		invoiceNotes = '';
		recipients = [];
		sendResult = null;
		sendSubject = '';
		sendBody = '';
		panelError = '';
		pdfLoading = false;
		generatorLoading = false;
	}

	function goToForm() {
		panelStep = 'form';
		generatedInvoice = null;
		panelError = '';
		generatorLoading = false;
		extraLines = [];
		invoiceNumber = '';
		invoiceNotes = '';
		resetPdfOverrides();
	}

	function goToDetails() {
		panelStep = 'details';
		panelError = '';
	}

	function goToPreview() {
		panelStep = 'preview';
	}

	function goBackToForm() {
		panelStep = 'form';
	}

	// Extra line management
	function addExtraLine() {
		extraLines = [...extraLines, { line_type: 'adjustment', description: '', quantity: 1, unit_price: 0 }];
	}

	function removeExtraLine(index: number) {
		extraLines = extraLines.filter((_, i) => i !== index);
	}

	// Compute preview data
	$: rentUnitPrice = selectedUnit ? parseFloat(selectedUnit.rent_unit_price) : 0;
	$: rentQuantity = selectedUnit?.billing_interval_months ?? 1;
	// What the period is billed: quantity x unit price.
	$: rentAmount = selectedUnit ? parseFloat(selectedUnit.rent_period_total) : 0;
	$: extraTotal = extraLines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0);
	$: grandTotal = rentAmount + extraTotal;
	$: previewLines = [
		{
			line_type: 'rent',
			description: `Loyer du ${formatDate(selectedPeriod?.period_start ?? '')} au ${formatDate(selectedPeriod?.period_end ?? '')}`,
			quantity: rentQuantity,
			unit_price: rentUnitPrice,
			amount: rentAmount
		},
		...extraLines
			.filter((l) => l.description && l.unit_price > 0)
			.map((l) => ({
				line_type: l.line_type,
				description: l.description,
				quantity: l.quantity,
				unit_price: l.unit_price,
				amount: l.quantity * l.unit_price
			}))
	];

	async function confirmGenerate() {
		if (!selectedUnit || !selectedPeriod?.period_start) return;
		generatorLoading = true;
		panelError = '';
		try {
			const payload: import('$lib/api/types').InvoiceGeneratePayload = {
				lease_id: selectedUnit.lease_id,
				period_start: selectedPeriod.period_start,
				invoice_date: invoiceDate,
				invoice_number: invoiceNumber.trim(),
				pdf_overrides: {
					pdf_show_rccm: ovShowRccm,
					pdf_show_nif: ovShowNif,
					pdf_bank_display: ovBankDisplay,
					pdf_selected_bank_indices: ovSelectedBankIndices,
					pdf_signatory_id: ovSignatory
				}
			};
			const validExtras = extraLines.filter((l) => l.description && l.unit_price > 0);
			if (validExtras.length > 0) {
				payload.extra_lines = validExtras;
			}
			if (invoiceNotes.trim()) {
				payload.notes = invoiceNotes.trim();
			}
			generatedInvoice = await api.invoices.generate(payload);
			panelStep = 'success';
			load();
		} catch (e) {
			panelError = e instanceof Error ? e.message : 'Error generating invoice';
		} finally {
			generatorLoading = false;
		}
	}

	$: validRecipients = recipients.map((r) => r.trim()).filter((r) => r.includes('@'));

	async function goToSend() {
		if (!existingInvoice) return;
		panelStep = 'send';
		sendResult = null;
		panelError = '';
		loadingDraft = true;
		try {
			const draft = await api.invoices.emailPreview(existingInvoice.id);
			sendSubject = draft.subject;
			sendBody = draft.body;
			recipients = [draft.default_recipient || ''];
		} catch (e) {
			panelError = e instanceof Error ? e.message : 'Error';
		} finally {
			loadingDraft = false;
		}
	}

	async function sendInvoice() {
		if (!existingInvoice || validRecipients.length === 0) return;
		sending = true;
		panelError = '';
		try {
			sendResult = await api.invoices.send(existingInvoice.id, {
				recipients: validRecipients,
				subject: sendSubject.trim(),
				body: sendBody
			});
		} catch (e) {
			panelError = e instanceof Error ? e.message : 'Error';
		} finally {
			sending = false;
		}
	}

	async function downloadInvoicePdf(invoiceId: number, invoiceNumber?: string) {
		pdfLoading = true;
		try {
			const token = getAccessToken();
			const res = await fetch(api.invoices.pdfUrl(invoiceId), {
				headers: token ? { Authorization: `Bearer ${token}` } : {}
			});
			if (!res.ok) throw new Error(`PDF error: ${res.status}`);
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = invoiceNumber ? `${invoiceNumber}.pdf` : `invoice-${invoiceId}.pdf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e) {
			panelError = e instanceof Error ? e.message : 'PDF download failed';
		} finally {
			pdfLoading = false;
		}
	}

	async function voidAndRegenerate() {
		if (!existingInvoice) return;
		const reason = prompt('Reason for voiding this invoice:');
		if (!reason) return;
		try {
			await api.invoices.void(existingInvoice.id, reason);
			existingInvoice = null;
			if (selectedPeriod) {
				selectedPeriod.invoice_id = null;
				selectedPeriod.status = 'future';
			}
			goToForm();
		} catch (e) {
			panelError = e instanceof Error ? e.message : 'Error voiding invoice';
		}
	}
</script>

<svelte:head><title>{$t('schedule.title')} – RealEstate</title></svelte:head>

<div class="space-y-5">
	<!-- Hero Header -->
	<div class="px-6 py-5 flex items-center justify-between" style="background: #031927">
		<div>
			<h1 class="text-xl font-bold text-white tracking-tight">{$t('schedule.title')}</h1>
			<p class="text-sm mt-0.5" style="color: #9dd1f1">{$t('schedule.subtitle')}</p>
		</div>
		<div class="flex p-1 gap-1" style="background: rgba(255,255,255,0.1)">
			<button
				class="px-4 py-1.5 text-sm font-medium transition-all duration-150"
				style={viewMode === 'grid' ? 'background: #fff; color: #031927' : 'background: transparent; color: rgba(255,255,255,0.7)'}
				on:click={() => (viewMode = 'grid')}
			>{$t('common.grid')}</button>
			<button
				class="px-4 py-1.5 text-sm font-medium transition-all duration-150"
				style={viewMode === 'cards' ? 'background: #fff; color: #031927' : 'background: transparent; color: rgba(255,255,255,0.7)'}
				on:click={() => (viewMode = 'cards')}
			>{$t('common.cards')}</button>
		</div>
	</div>

	<!-- Controls bar -->
	<div class="flex flex-wrap items-center gap-3">
		<!-- View type toggle -->
		<div class="flex p-1 gap-0.5" style="background: #c8e0f4">
			<button
				class="px-4 py-1.5 text-sm font-semibold transition-all duration-150"
				style={viewType === '6m' ? 'background: #031927; color: white' : 'background: transparent; color: #508aa8'}
				on:click={() => { viewType = '6m'; load(); }}
			>{$t('schedule.view6m')}</button>
			<button
				class="px-4 py-1.5 text-sm font-semibold transition-all duration-150"
				style={viewType === '12m' ? 'background: #031927; color: white' : 'background: transparent; color: #508aa8'}
				on:click={() => { viewType = '12m'; load(); }}
			>{$t('schedule.view12m')}</button>
		</div>

		<!-- Period navigation -->
		<div class="flex items-center gap-1">
			<button
				class="px-3 py-1.5 text-sm font-bold transition-colors hover:opacity-80"
				style="background: #c8e0f4; color: #031927"
				on:click={navigatePrev}
				title={$t('schedule.prevPeriod')}
			>&#9664;</button>
			<span class="min-w-[160px] px-2 text-center text-sm font-semibold" style="color: #031927">
				{periodLabel}
			</span>
			<button
				class="px-3 py-1.5 text-sm font-bold transition-colors hover:opacity-80"
				style="background: #c8e0f4; color: #031927"
				on:click={navigateNext}
				title={$t('schedule.nextPeriod')}
			>&#9654;</button>
		</div>

		<select
			class="input w-44"
			bind:value={propertyFilter}
			on:change={() => load()}
		>
			<option value="">{$t('schedule.selectProperty')}</option>
			{#each propertyOptions as p}
				<option value={p.id}>{p.name}</option>
			{/each}
		</select>
	</div>

	{#if error}
		<div class="text-sm text-red-600">{error}</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Spinner />
		</div>
	{:else if schedule}
		<!-- GRID VIEW -->
		{#if viewMode === 'grid'}
			<div class="overflow-x-auto border border-gray-100 bg-white">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200" style="background: #031927">
							<th
								class="sticky left-0 z-10 min-w-[200px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide"
								style="background: #031927; color: #9dd1f1"
								>{$t('schedule.unit')} / {$t('schedule.tenant')}</th
							>
							{#each periodMonths as month}
								<th
									class="min-w-[120px] px-2 py-3 text-center text-xs font-semibold tracking-wide"
									style={isCurrentMonth(month) ? 'background: #c8e0f4; color: #031927' : 'background: #031927; color: #9dd1f1'}
								>
									{formatMonth(month)}
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each schedule.properties as prop}
							<!-- Property header row -->
							<tr class="border-t border-gray-100" style="background: #eff6ff">
								<td
									class="sticky left-0 z-10 px-4 py-2 font-semibold"
									style="background: #eff6ff; color: #031927"
									colspan="1"
								>
									{prop.name}{#if ownerByPropertyId[prop.id]}<span class="ml-1 font-normal" style="color: #508aa8">/ {ownerByPropertyId[prop.id]}</span>{/if}
								</td>
								{#each periodMonths as _}
									<td style="background: #eff6ff"></td>
								{/each}
							</tr>
							<!-- Unit rows -->
							{#each prop.units as unit}
								<tr class="border-t border-gray-100 hover:bg-gray-50/50">
									<td class="sticky left-0 z-10 bg-white px-4 py-2.5">
										<div class="font-medium text-gray-900">{unit.unit_name}</div>
										<div class="text-xs text-gray-500">
											{unit.tenant_name} · {formatCurrency(unit.rent_period_total, unit.currency)}{unit.billing_interval_months === 1 ? '/mo' : ` / ${unit.billing_interval_months} mo`}
										</div>
									</td>
									{#each periodMonths as month}
										{@const period = getPeriodForMonth(unit.periods, month)}
										{@const cfg = statusConfig[period?.status ?? 'no_lease']}
										<td
											class="px-1 py-2 text-center"
											style={isCurrentMonth(month) ? 'background: #f0f7ff' : ''}
										>
											{#if period && period.status !== 'no_lease'}
												<button
													class="mx-auto w-full px-1.5 py-1 text-xs font-medium transition-all hover:ring-2 cursor-pointer"
													style="background: {cfg.bg}; color: {cfg.color}; border: 1px solid {cfg.border}"
													on:click={() => openPanel(period, unit, prop)}
												>
													<div>{getPeriodStatusLabel(period.status)}</div>
													{#if period.amount}
														<div class="text-[10px] opacity-75">
															{formatCompact(period.amount, unit.currency)}
														</div>
													{/if}
												</button>
											{:else}
												<div class="text-xs" style="color: #d1d5db">–</div>
											{/if}
										</td>
									{/each}
								</tr>
							{/each}
						{/each}
						{#if schedule.properties.length === 0}
							<tr>
								<td
									colspan={periodMonths.length + 1}
									class="px-4 py-12 text-center text-gray-500"
								>
									{$t('schedule.noUnits')}
								</td>
							</tr>
						{/if}
					</tbody>
				</table>
			</div>

		<!-- CARDS VIEW -->
		{:else}
			<div class="space-y-6">
				{#each schedule.properties as prop}
					<div class="border border-gray-200 bg-white">
						<!-- Property header -->
						<button
							class="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
							on:click={() => toggleCollapse(prop.id)}
						>
							<div>
								<h2 class="font-semibold text-gray-900">{prop.name}{#if ownerByPropertyId[prop.id]}<span class="ml-1 font-normal text-gray-400">/ {ownerByPropertyId[prop.id]}</span>{/if}</h2>
								<p class="text-xs text-gray-500">
									{prop.units.length} unit{prop.units.length !== 1 ? 's' : ''}
								</p>
							</div>
							<svg
								class="h-5 w-5 text-gray-400 transition-transform {collapsed[prop.id] ? '' : 'rotate-180'}"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M19 9l-7 7-7-7"
								/>
							</svg>
						</button>

						{#if !collapsed[prop.id]}
							<div class="space-y-3 border-t border-gray-100 p-4">
								{#each prop.units as unit}
									<div class="border border-gray-100 p-3">
										<!-- Unit header -->
										<div class="mb-3 flex items-center justify-between">
											<div>
												<span class="font-medium text-gray-900"
													>{unit.unit_name}</span
												>
												<span class="ml-2 text-sm text-gray-500"
													>{unit.tenant_name}</span
												>
											</div>
											<div class="text-sm text-gray-600">
												{formatCurrency(unit.rent_period_total, unit.currency)}
												<span class="text-xs text-gray-400">
													/ {unit.billing_interval_months === 1
														? 'month'
														: `${unit.billing_interval_months} months`}
												</span>
											</div>
										</div>
										<!-- Timeline -->
										<div class="flex gap-1.5 overflow-x-auto">
											{#each periodMonths as month}
												{@const period = getPeriodForMonth(
													unit.periods,
													month
												)}
												{@const cfg =
													statusConfig[period?.status ?? 'no_lease']}
												<button
													class="flex min-w-[70px] flex-1 flex-col items-center border p-2 transition-all {period && period.status !== 'no_lease' ? 'hover:ring-2 cursor-pointer' : 'cursor-default'}"
													style="background: {period && period.status !== 'no_lease' ? cfg.bg : 'white'}; border-color: {isCurrentMonth(month) ? '#508aa8' : (period && period.status !== 'no_lease' ? cfg.border : '#e5e7eb')}; {isCurrentMonth(month) ? 'box-: 0 0 0 2px #9dd1f1' : ''}"
													on:click={() => {
														if (period && period.status !== 'no_lease') {
															openPanel(period, unit, prop);
														}
													}}
												>
													<div
														class="text-[10px] font-medium uppercase"
														style="color: {isCurrentMonth(month) ? '#031927' : '#94a3b8'}"
													>
														{formatMonthShort(month)}
													</div>
													{#if period && period.status !== 'no_lease'}
														<div
															class="mt-1 text-xs font-semibold"
															style="color: {cfg.color}"
														>
															{getPeriodStatusLabel(period.status)}
														</div>
														{#if period.amount}
															<div
																class="mt-0.5 text-[10px] opacity-75"
																style="color: {cfg.color}"
															>
																{formatCompact(
																	period.amount,
																	unit.currency
																)}
															</div>
														{/if}
													{:else}
														<div class="mt-1 text-xs text-gray-300">
															–
														</div>
													{/if}
												</button>
											{/each}
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
				{#if schedule.properties.length === 0}
					<div
						class="border border-gray-200 bg-white px-4 py-12 text-center text-gray-500"
					>
						{$t('schedule.noUnits')}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Legend -->
		<div class="flex flex-wrap items-center gap-3 text-xs text-gray-500">
			<span class="font-semibold" style="color: #031927">Legend:</span>
			{#each Object.entries(statusConfig).filter(([k]) => k !== 'no_lease' && k !== 'void') as [key, cfg]}
				<span class="flex items-center gap-1.5">
					<span class="inline-block h-3 w-3" style="background: {cfg.bg}; border: 1px solid {cfg.border}"></span>
					<span style="color: {cfg.color}; font-weight: 500">{getPeriodStatusLabel(key)}</span>
				</span>
			{/each}
		</div>
	{/if}
</div>

<!-- ═══════════════════════════════════════════════ -->
<!-- UNIFIED SLIDE-OVER PANEL                       -->
<!-- ═══════════════════════════════════════════════ -->
{#if panelOpen}
	<div class="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
		<!-- Backdrop -->
		<div class="absolute inset-0 bg-slate-900/30" on:click={closePanel} role="presentation"></div>

		<!-- Panel -->
		<div class="relative flex h-full w-full max-w-2xl flex-col bg-white animate-slide-in">
			<!-- ─── HEADER ─── -->
			<div class="flex-shrink-0 border-b border-gray-200 px-6 py-4">
				<div class="flex items-center justify-between">
					<div class="min-w-0 flex-1">
						{#if panelStep === 'details'}
							<div class="flex items-center gap-3">
								{#if selectedPeriod}
									<span class="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center" style="background: {statusConfig[selectedPeriod.status].bg}">
										<span class="h-2.5 w-2.5 rounded-full" style="background: {statusConfig[selectedPeriod.status].dotColor}"></span>
									</span>
								{/if}
								<div class="min-w-0">
									<h2 class="truncate text-lg font-semibold text-gray-900">{selectedUnit?.unit_name ?? ''}</h2>
									<p class="truncate text-sm text-gray-500">{selectedProperty?.name ?? ''} · {selectedUnit?.tenant_name ?? ''}</p>
								</div>
							</div>
						{:else if panelStep === 'form'}
							<h2 class="text-lg font-semibold text-gray-900">{$t('schedule.generateInvoice')}</h2>
							<p class="text-sm text-gray-500">{selectedUnit?.unit_name ?? ''} · {selectedUnit?.tenant_name ?? ''}</p>
						{:else if panelStep === 'preview'}
							<h2 class="text-lg font-semibold text-gray-900">{$t('schedule.previewInvoice')}</h2>
							<p class="text-sm text-gray-500">{$t('schedule.reviewBeforeGenerating')}</p>
						{:else if panelStep === 'success'}
							<h2 class="text-lg font-semibold text-gray-900">{$t('schedule.summary.generated')}</h2>
							<p class="text-sm font-medium text-green-600">{$t('schedule.generatedSuccessfully')}</p>
						{/if}
					</div>
					<button on:click={closePanel} class="ml-4 flex-shrink-0 p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>

			<!-- ─── BODY ─── -->
			<div class="flex-1 overflow-y-auto px-6 py-5">

				<!-- ═══ STEP: DETAILS ═══ -->
				{#if panelStep === 'details' && selectedPeriod && selectedUnit}
					<div class="space-y-5">
						<!-- Status + Period header -->
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2 text-sm text-gray-500">
								<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
								</svg>
								{formatDate(selectedPeriod.period_start ?? '')} — {formatDate(selectedPeriod.period_end ?? '')}
							</div>
							<span class="inline-flex items-center border px-2.5 py-1 text-xs font-bold" style="background: {statusConfig[selectedPeriod.status].bg}; color: {statusConfig[selectedPeriod.status].color}; border-color: {statusConfig[selectedPeriod.status].border}">
								{getPeriodStatusLabel(selectedPeriod.status)}
							</span>
						</div>

						<!-- Info cards -->
						<div class="grid grid-cols-2 gap-3">
							<div class="border border-gray-100 bg-gray-50/80 p-4">
								<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.rent')}</p>
								<p class="mt-1.5 text-xl font-bold text-gray-900">
									{formatCurrency(selectedUnit.rent_period_total, selectedUnit.currency)}
								</p>
								<p class="mt-0.5 text-xs text-gray-400">
									{$t('common.every')} {selectedUnit.billing_interval_months === 1 ? $t('units.month') : `${selectedUnit.billing_interval_months} ${$t('units.months')}`}
								</p>
							</div>
							<div class="border border-gray-100 bg-gray-50/80 p-4">
								<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.amount')}</p>
								<p class="mt-1.5 text-xl font-bold text-gray-900">
									{selectedPeriod.amount ? formatCurrency(selectedPeriod.amount, selectedUnit.currency) : '—'}
								</p>
								{#if selectedPeriod.paid}
									<p class="mt-0.5 text-xs font-medium text-green-600">
										{formatCurrency(selectedPeriod.paid, selectedUnit.currency)} {$t('schedule.paid')}
									</p>
								{:else}
									<p class="mt-0.5 text-xs text-gray-400">{$t('schedule.noPaymentsYet')}</p>
								{/if}
							</div>
						</div>

						<!-- Invoice section -->
						{#if loadingInvoice}
							<div class="flex items-center justify-center py-8">
								<Spinner />
							</div>
						{:else if existingInvoice}
							<!-- Existing Invoice Card -->
							<div class="space-y-4">
								<div class="flex items-center gap-2">
									<svg class="h-4 w-4" style="color: #508aa8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
									<h3 class="text-sm font-semibold text-gray-700">{$t('schedule.invoiceDetails')}</h3>
								</div>

								<div class="border p-4" style="border-color: #c8e0f4; background: #f7fbfe">
									<!-- Invoice header -->
									<div class="flex items-start justify-between">
										<div>
											<p class="text-base font-bold text-gray-900">{existingInvoice.invoice_number}</p>
											<p class="mt-0.5 text-xs text-gray-500">{$t('schedule.dueDate')} {formatDate(existingInvoice.due_date)}</p>
										</div>
										<div class="text-right">
											<p class="text-lg font-bold text-gray-900">{formatCurrency(existingInvoice.total_amount, existingInvoice.currency)}</p>
											<p class="text-[10px] font-medium uppercase tracking-wide text-gray-400">Total</p>
										</div>
									</div>

									<!-- Payment progress bar -->
									{#if parseFloat(existingInvoice.total_amount) > 0}
										{@const paidPct = Math.min(100, (parseFloat(existingInvoice.paid_amount) / parseFloat(existingInvoice.total_amount)) * 100)}
										<div class="mt-4">
											<div class="flex justify-between text-[10px] font-medium text-gray-500">
												<span>{$t('schedule.paid')} {formatCurrency(existingInvoice.paid_amount, existingInvoice.currency)}</span>
												<span>{$t('schedule.balance')} {formatCurrency(existingInvoice.balance, existingInvoice.currency)}</span>
											</div>
											<div class="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-gray-200">
												<div
													class="h-full rounded-full transition-all duration-500 {paidPct >= 100 ? 'bg-green-500' : paidPct > 0 ? 'bg-primary-500' : 'bg-gray-300'}"
													style="width:{paidPct}%"
												></div>
											</div>
										</div>
									{/if}
								</div>

								<!-- Invoice lines breakdown -->
								{#if existingInvoice.lines && existingInvoice.lines.length > 0}
									<div class="border border-gray-100 bg-white">
										<div class="border-b border-gray-100 px-4 py-2.5">
											<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.lineItems')}</p>
										</div>
										<div class="divide-y divide-gray-50">
											{#each existingInvoice.lines as line}
												<div class="flex items-center justify-between px-4 py-2.5">
													<div class="min-w-0 flex-1">
														<p class="truncate text-sm text-gray-700">{line.description}</p>
														<p class="text-[10px] text-gray-400">
															{line.quantity} × {formatCurrency(line.unit_price, existingInvoice.currency)}
														</p>
													</div>
													<p class="ml-4 flex-shrink-0 text-sm font-semibold text-gray-900">
														{formatCurrency(line.amount, existingInvoice.currency)}
													</p>
												</div>
											{/each}
										</div>
									</div>
								{/if}
							</div>
						{:else if !selectedPeriod.invoice_id}
							<!-- No Invoice Yet -->
							<div class="border-2 border-dashed border-gray-200 px-6 py-10 text-center">
								<div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
									<svg class="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
								</div>
								<p class="mt-3 text-sm font-medium text-gray-900">{$t('schedule.noInvoiceGenerated')}</p>
								<p class="mt-1 text-xs text-gray-500">{$t('schedule.generateInvoiceForBillingPeriod')}</p>
							</div>
						{/if}

						{#if panelError}
							<div class="bg-red-50 p-3 text-sm text-red-600">{panelError}</div>
						{/if}
					</div>

				<!-- ═══ STEP: FORM ═══ -->
				{:else if panelStep === 'form' && selectedPeriod && selectedUnit}
					<div class="space-y-6">
						<!-- Period info banner -->
						<div class="border border-gray-200 bg-gray-50 p-4">
							<p class="text-sm font-semibold text-gray-900">
								{formatDate(selectedPeriod.period_start ?? '')} — {formatDate(selectedPeriod.period_end ?? '')}
							</p>
							<p class="mt-0.5 text-xs text-gray-600">{selectedUnit.unit_name} · {selectedUnit.tenant_name}</p>
						</div>

						<!-- Invoice Date -->
						<div>
							<label class="label" for="inv-date">{$t('schedule.dueDate')}</label>
							<input id="inv-date" class="input" type="date" bind:value={invoiceDate} />
						</div>
						<div>
							<label class="label" for="inv-number">{$t('schedule.invoiceNumber')}</label>
							<input
								id="inv-number"
								class="input"
								type="text"
								bind:value={invoiceNumber}
								placeholder={$t('schedule.invoiceNumberAuto')}
							/>
						</div>

						<!-- Rent line (read-only) -->
						<div>
							<h3 class="mb-2 text-sm font-semibold text-gray-700">{$t('schedule.rent')}</h3>
							<div class="flex items-center gap-3 border border-gray-200 bg-gray-50/80 p-4">
								<div class="flex-1">
									<p class="text-sm font-medium text-gray-900">
										Loyer du {formatDate(selectedPeriod.period_start ?? '')} au {formatDate(selectedPeriod.period_end ?? '')}
									</p>
									<p class="mt-0.5 text-xs text-gray-500">
										Qty: {rentQuantity} × {formatCurrency(String(rentUnitPrice), selectedUnit.currency)}
									</p>
								</div>
								<p class="text-base font-bold text-gray-900">{formatCurrency(selectedUnit.rent_period_total, selectedUnit.currency)}</p>
							</div>
						</div>

						<!-- Extra charges -->
						<div>
							<div class="mb-2 flex items-center justify-between">
								<h3 class="text-sm font-semibold text-gray-700">{$t('schedule.extraLines')}</h3>
								<button
									class="flex items-center gap-1 px-2.5 py-1 text-xs font-medium hover:opacity-80"
							style="color: #508aa8; background: #eff6ff"
									on:click={addExtraLine}
								>
									<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
									</svg>
									{$t('schedule.addLine')}
								</button>
							</div>
							{#if extraLines.length === 0}
								<p class="border border-dashed border-gray-200 px-4 py-5 text-center text-xs text-gray-400">
									No extra charges. Click "{$t('schedule.addLine')}" to add adjustments, parking fees, etc.
								</p>
							{:else}
								<div class="space-y-2">
									{#each extraLines as line, i}
										<div class="border border-gray-200 p-3">
											<div class="flex items-start gap-2">
												<select
													bind:value={line.line_type}
													class="input w-28 text-xs"
												>
													<option value="adjustment">Adjustment</option>
													<option value="other">Other</option>
												</select>
												<input
													type="text"
													bind:value={line.description}
													placeholder={$t('schedule.lineDescription')}
													class="input flex-1 text-sm"
												/>
												<button
													on:click={() => removeExtraLine(i)}
													class="p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
												>
													<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
													</svg>
												</button>
											</div>
											<div class="mt-2 flex items-center gap-2">
												<div class="flex-1">
													<label class="text-[10px] font-medium uppercase text-gray-400">Qty</label>
													<input
														type="number"
														bind:value={line.quantity}
														min="1"
														step="1"
														class="input mt-0.5 w-full text-sm"
													/>
												</div>
												<div class="flex-1">
													<label class="text-[10px] font-medium uppercase text-gray-400">{$t('schedule.lineAmount')}</label>
													<input
														type="number"
														bind:value={line.unit_price}
														min="0"
														step="100"
														class="input mt-0.5 w-full text-sm"
													/>
												</div>
												<div class="w-24 text-right">
													<label class="text-[10px] font-medium uppercase text-gray-400">{$t('schedule.amount')}</label>
													<p class="mt-1.5 text-sm font-semibold text-gray-900">
														{formatCurrency(String(line.quantity * line.unit_price), selectedUnit.currency)}
													</p>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<!-- Notes -->
						<div>
							<label for="invoice-notes" class="mb-1 block text-sm font-semibold text-gray-700">{$t('schedule.customNotes')}</label>
							<textarea
								id="invoice-notes"
								bind:value={invoiceNotes}
								rows="2"
								placeholder={$t('common.optional')}
								class="input w-full text-sm"
							></textarea>
						</div>

						<!-- ── PDF Display Options (collapsible) ── -->
						<div class="border border-gray-200">
							<button
								type="button"
								class="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-gray-50"
								on:click={() => (pdfOptionsExpanded = !pdfOptionsExpanded)}
							>
								<div class="flex items-center gap-2.5">
									<div>
										<span class="text-sm font-semibold text-gray-700">{$t('schedule.pdfOptions.title')}</span>
										<p class="text-[11px] text-gray-400">{$t('schedule.pdfOptions.description')}</p>
									</div>
								</div>
								<svg
									class="h-5 w-5 text-gray-400 transition-transform {pdfOptionsExpanded ? 'rotate-180' : ''}"
									fill="none" stroke="currentColor" viewBox="0 0 24 24"
								>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
								</svg>
							</button>

							{#if pdfOptionsExpanded}
								<div class="space-y-4 border-t border-gray-100 px-4 py-4">

									<!-- Legal references -->
									<div>
										<p class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.legalReferences')}</p>
										<div class="flex flex-wrap gap-2">
											<label class="flex cursor-pointer items-center gap-2 border px-3 py-2 text-xs transition-colors {ovShowRccm ? 'border-primary-200 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}">
												<input type="checkbox" bind:checked={ovShowRccm} class="h-3.5 w-3.5 border-gray-300 text-primary-600 focus:ring-primary-500" />
												{$t('schedule.pdfOptions.showRccm')}
												{#if $companyInfo?.rccm}
													<span class="text-[10px] opacity-60">{$companyInfo.rccm}</span>
												{/if}
											</label>
											<label class="flex cursor-pointer items-center gap-2 border px-3 py-2 text-xs transition-colors {ovShowNif ? 'border-primary-200 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}">
												<input type="checkbox" bind:checked={ovShowNif} class="h-3.5 w-3.5 border-gray-300 text-primary-600 focus:ring-primary-500" />
												{$t('schedule.pdfOptions.showNif')}
												{#if $companyInfo?.nif}
													<span class="text-[10px] opacity-60">{$companyInfo.nif}</span>
												{/if}
											</label>
										</div>
									</div>

									<!-- Bank details -->
									<div>
										<p class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.pdfOptions.bankAccounts')}</p>
										<div class="inline-flex border border-gray-200 bg-gray-50 p-0.5">
											<button type="button" on:click={() => (ovBankDisplay = 'none')}
												class="px-3 py-1.5 text-xs font-medium transition-all {ovBankDisplay === 'none' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
												{$t('common.none')}
											</button>
											<button type="button" on:click={() => (ovBankDisplay = 'all')}
												class="px-3 py-1.5 text-xs font-medium transition-all {ovBankDisplay === 'all' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
												{$t('common.all')}
											</button>
											<button type="button" on:click={() => (ovBankDisplay = 'selected')}
												class="px-3 py-1.5 text-xs font-medium transition-all {ovBankDisplay === 'selected' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
												Select
											</button>
										</div>

										{#if ovBankDisplay === 'selected' && ($companyInfo?.bank_accounts?.length ?? 0) > 0}
											<div class="mt-2 space-y-1.5">
												{#each ($companyInfo?.bank_accounts ?? []) as bank, i}
													{#if bank.bank_name || bank.account_number}
														<label class="flex cursor-pointer items-center gap-2 border px-3 py-2 text-xs transition-colors {ovSelectedBankIndices.includes(i) ? 'border-primary-200 bg-primary-50' : 'border-gray-200 hover:bg-gray-50'}">
															<input
																type="checkbox"
																checked={ovSelectedBankIndices.includes(i)}
																on:change={() => toggleOvBankIndex(i)}
																class="h-3.5 w-3.5 border-gray-300 text-primary-600 focus:ring-primary-500"
															/>
															<span class="font-medium text-gray-700">{bank.bank_name}</span>
															<span class="text-gray-400">—</span>
															<span class="text-gray-500">{bank.account_number}</span>
														</label>
													{/if}
												{/each}
											</div>
										{/if}
									</div>

									<!-- Signatory -->
									<div>
										<p class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.pdfOptions.signatory')}</p>
										<div class="inline-flex border border-gray-200 bg-gray-50 p-0.5">
											<button type="button" on:click={() => (ovSignatory = null)}
												class="px-3 py-1.5 text-xs font-medium transition-all {ovSignatory === null ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
												{$t('common.none')}
											</button>
											{#each signatories as signatory}
												<button type="button" on:click={() => (ovSignatory = signatory.id)}
													class="px-3 py-1.5 text-xs font-medium transition-all {ovSignatory === signatory.id ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
													{signatory.label}
												</button>
											{/each}
										</div>

										{#if ovSignatoryPreview}
											<div class="mt-2 space-y-2">
												<div class="flex items-center gap-3">
													<span class="bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-700">
														{ovSignatoryPreview.label}{ovSignatoryPreview.name ? ` : ${ovSignatoryPreview.name}` : ''}
													</span>
												</div>
												{#if ovSignatureImageUrl}
													<div class="flex justify-end">
														<img src={ovSignatureImageUrl} alt="Signature preview" class="max-h-14 max-w-[160px] border border-gray-100 bg-white p-1 object-contain" />
													</div>
												{:else}
													<p class="text-right text-[11px] italic text-gray-400">{$t('schedule.pdfOptions.noSignatureUploaded')}</p>
												{/if}
											</div>
										{/if}
									</div>

									<!-- Reset to defaults -->
									<button
										type="button"
										on:click={resetPdfOverrides}
										class="text-xs text-gray-400 underline decoration-gray-300 hover:text-gray-600"
									>
										Reset to company defaults
									</button>
								</div>
							{/if}
						</div>

					</div>

				<!-- ═══ STEP: PREVIEW ═══ -->
				{:else if panelStep === 'preview'}
					<div class="flex justify-center overflow-auto">
						<div class="origin-top scale-[0.85] transform">
							<InvoicePreview
								invoiceNumber={invoiceNumber.trim() || "INV-XXXXXX"}
								issueDate={new Date().toISOString().split('T')[0]}
								dueDate={selectedPeriod?.period_start ?? ''}
								periodStart={selectedPeriod?.period_start ?? ''}
								periodEnd={selectedPeriod?.period_end ?? ''}
								currency={selectedUnit?.currency ?? 'XAF'}
								tenantName={selectedUnit?.tenant_name ?? ''}
								unitName={selectedUnit?.unit_name ?? ''}
								propertyName={selectedProperty?.name ?? ''}
								lines={previewLines}
								totalAmount={grandTotal}
								notes={invoiceNotes}
								companyName={$companyInfo?.company_name ?? ''}
								companyAddress={$companyInfo?.address ?? ''}
								companyCity={[$companyInfo?.city, $companyInfo?.country].filter(Boolean).join(', ')}
								companyPhone={$companyInfo?.phone_numbers?.join(' / ') ?? ''}
								companyEmail={$companyInfo?.email ?? ''}
								companyLogoUrl={mediaUrl($companyInfo?.logo_url ?? null)}
								companyBankAccounts={$companyInfo?.bank_accounts ?? []}
								companyRccm={$companyInfo?.rccm ?? ''}
								companyNif={$companyInfo?.nif ?? ''}
								pdfSignatory={ovSignatoryPreview ?? null}
								pdfShowRccm={ovShowRccm}
								pdfShowNif={ovShowNif}
								pdfBankDisplay={ovBankDisplay}
								pdfSelectedBankIndices={ovSelectedBankIndices}
							/>
						</div>
					</div>

				<!-- ═══ STEP: SUCCESS ═══ -->
				{:else if panelStep === 'success' && generatedInvoice}
					<div class="flex flex-col items-center py-8">
						<!-- Success icon -->
						<div class="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
							<svg class="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
							</svg>
						</div>
						<h3 class="mt-4 text-lg font-semibold text-gray-900">{$t('schedule.summary.generated')}</h3>
						<p class="mt-1 text-sm text-gray-500">{generatedInvoice.invoice_number}</p>

						<!-- Invoice summary -->
						<div class="mt-6 w-full max-w-sm border border-gray-200 p-4">
							<div class="space-y-2.5 text-sm">
								<div class="flex justify-between">
									<span class="text-gray-500">{$t('schedule.tenant')}</span>
									<span class="font-medium text-gray-900">{generatedInvoice.tenant_name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">{$t('schedule.period')}</span>
									<span class="font-medium text-gray-900">{formatDate(generatedInvoice.period_start)} — {formatDate(generatedInvoice.period_end)}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">{$t('schedule.dueDate')}</span>
									<span class="font-medium text-gray-900">{formatDate(generatedInvoice.due_date)}</span>
								</div>
								<div class="flex justify-between border-t border-gray-100 pt-2.5">
									<span class="font-semibold text-gray-900">Total</span>
									<span class="text-lg font-bold" style="color: #508aa8">{formatCurrency(generatedInvoice.total_amount, generatedInvoice.currency)}</span>
								</div>
							</div>
						</div>

						<!-- Lines breakdown -->
						{#if generatedInvoice.lines && generatedInvoice.lines.length > 0}
							<div class="mt-4 w-full max-w-sm">
								<p class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('schedule.lineItems')}</p>
								<div class="border border-gray-100 divide-y divide-gray-50">
									{#each generatedInvoice.lines as line}
										<div class="flex items-center justify-between px-4 py-2.5 text-sm">
											<span class="text-gray-600">{line.description}</span>
											<span class="font-medium text-gray-900">{formatCurrency(line.amount, generatedInvoice.currency)}</span>
										</div>
									{/each}
								</div>
							</div>
						{/if}

					</div>

				<!-- ═══ STEP: SEND ═══ -->
				{:else if panelStep === 'send' && existingInvoice}
					<div class="space-y-4">
						<div>
							<p class="text-sm font-semibold text-gray-900">{$t('schedule.sendTitle')}</p>
							<p class="mt-0.5 text-xs text-gray-500">
								{existingInvoice.invoice_number} · {$t('schedule.attachmentNote')}
							</p>
						</div>

						{#if loadingDraft}
							<p class="py-8 text-center text-sm text-gray-500">{$t('common.loading')}</p>
						{:else}
							<div>
								<label class="label" for="s-rcpt-0">{$t('schedule.recipients')}</label>
								{#each recipients as _, i}
									<div class="mb-2 flex gap-2">
										<input
											id={`s-rcpt-${i}`}
											class="input"
											type="email"
											bind:value={recipients[i]}
											placeholder={$t('schedule.recipientPlaceholder')}
										/>
										{#if recipients.length > 1}
											<button
												class="btn-secondary btn-sm !text-red-700"
												on:click={() => (recipients = recipients.filter((_, j) => j !== i))}
												aria-label={$t('common.delete')}
											>×</button>
										{/if}
									</div>
								{/each}
								<button class="btn-secondary btn-sm" on:click={() => (recipients = [...recipients, ''])}>
									{$t('schedule.addRecipient')}
								</button>
							</div>

							<div>
								<label class="label" for="s-subject">{$t('schedule.subject')}</label>
								<input id="s-subject" class="input" type="text" bind:value={sendSubject} />
							</div>

							<div>
								<p class="label">{$t('schedule.message')}</p>
								<p class="mb-1 text-xs text-gray-500">{$t('schedule.messageHint')}</p>
								<RichTextEditor content={sendBody} on:change={(e) => (sendBody = e.detail)} />
							</div>

							{#if sendResult}
								<div class="space-y-1 text-xs">
									{#if sendResult.sent.length}
										<p class="text-green-700">{$t('schedule.sentTo')} : {sendResult.sent.join(', ')}</p>
									{/if}
									{#if sendResult.failed.length}
										<p class="text-red-700">{$t('schedule.sendFailed')} : {sendResult.failed.join(', ')}</p>
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				{/if}

				{#if panelError && panelStep !== 'details'}
					<div class="mt-4 bg-red-50 p-3 text-sm text-red-600">{panelError}</div>
				{/if}
			</div>

			<!-- ─── FOOTER ─── -->
			<div class="flex-shrink-0 border-t border-gray-200 px-6 py-4">
				{#if panelStep === 'details'}
					<div class="flex items-center justify-between">
						<button class="btn btn-secondary" on:click={closePanel}>{$t('common.close')}</button>
						<div class="flex gap-2">
							{#if existingInvoice}
								<!-- Download PDF -->
								<button
									class="btn btn-secondary"
									disabled={pdfLoading}
									on:click={() => { if (existingInvoice) downloadInvoicePdf(existingInvoice.id, existingInvoice.invoice_number); }}
								>
									{#if pdfLoading}
										<svg class="mr-1.5 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
											<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
											<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
										</svg>
										Downloading…
									{:else}
										<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
										</svg>
										{$t('schedule.downloadPdf')}
									{/if}
								</button>
								<!-- Send by email -->
								<button class="btn btn-secondary" on:click={goToSend}>
									{$t('schedule.sendByEmail')}
								</button>
								<!-- Regenerate (only if not fully paid) -->
								{#if existingInvoice.status !== 'paid'}
									<button class="btn btn-danger" on:click={voidAndRegenerate}>
										<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
										</svg>
										{$t('schedule.voidInvoice')}
									</button>
								{/if}
							{:else if !selectedPeriod?.invoice_id && !loadingInvoice}
								<!-- Generate Invoice -->
								<button class="btn btn-primary" on:click={goToForm}>
									<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
									</svg>
									{$t('schedule.generateInvoice')}
								</button>
							{/if}
						</div>
					</div>

				{:else if panelStep === 'send'}
					<div class="flex items-center justify-between">
						<button class="btn btn-secondary" on:click={() => (panelStep = 'details')}>
							{$t('schedule.backToDetails')}
						</button>
						<button
							class="btn btn-primary"
							on:click={sendInvoice}
							disabled={sending || loadingDraft || validRecipients.length === 0 || !sendSubject.trim()}
						>
							{sending ? $t('schedule.sending') : $t('schedule.sendNow')}
						</button>
					</div>

				{:else if panelStep === 'form'}
					<!-- Grand total bar -->
					<div class="mb-4 flex items-center justify-between bg-primary-600 px-4 py-3">
						<span class="text-sm font-medium text-primary-100">{$t('schedule.grandTotal')}</span>
						<span class="text-lg font-bold text-white">{selectedUnit ? formatCurrency(String(grandTotal), selectedUnit.currency) : ''}</span>
					</div>
					<div class="flex justify-between">
						<button class="btn btn-secondary" on:click={goToDetails}>
							<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
							</svg>
							Back
						</button>
						<button class="btn btn-primary" on:click={goToPreview}>
							{$t('schedule.previewInvoice')}
							<svg class="ml-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
							</svg>
						</button>
					</div>

				{:else if panelStep === 'preview'}
					<div class="flex justify-between">
						<button class="btn btn-secondary" on:click={goBackToForm}>
							<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
							</svg>
							Back
						</button>
						<button
							class="btn btn-primary"
							on:click={confirmGenerate}
							disabled={generatorLoading}
						>
							{#if generatorLoading}
								<svg class="mr-2 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
								</svg>
								{$t('common.saving')}
							{:else}
								{$t('schedule.generateInvoice')}
								<svg class="ml-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
								</svg>
							{/if}
						</button>
					</div>

				{:else if panelStep === 'success'}
					<div class="flex justify-between">
						<button class="btn btn-secondary" disabled={pdfLoading} on:click={() => { if (generatedInvoice) downloadInvoicePdf(generatedInvoice.id, generatedInvoice.invoice_number); }}>
							{#if pdfLoading}
								<svg class="mr-2 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
								</svg>
								Downloading…
							{:else}
								<svg class="mr-1.5 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								{$t('schedule.downloadPdf')}
							{/if}
						</button>
						<button class="btn btn-primary" on:click={closePanel}>{$t('common.close')}</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	@keyframes slideIn {
		from {
			transform: translateX(100%);
		}
		to {
			transform: translateX(0);
		}
	}
	.animate-slide-in {
		animation: slideIn 0.25s ease-out;
	}
</style>

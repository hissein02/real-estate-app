<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api } from '$lib/api/client';
	import type { Payment, Tenant, Invoice } from '$lib/api/types';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { PAYMENT_STATUS_COLORS } from '$lib/utils/status';

	// --- Payment List State ---
	let payments: Payment[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';

	// --- Record Payment State ---
	let showRecorder = false;
	let step: 'form' | 'confirm' | 'success' = 'form';
	let saving = false;
	let saveError = '';

	// Tenant search
	let tenants: Tenant[] = [];
	let tenantSearch = '';
	let filteredTenants: Tenant[] = [];
	let showTenantDropdown = false;
	let selectedTenant: Tenant | null = null;

	// Tenant's active leases (to find the lease for selected invoices)
	interface TenantLease {
		id: number;
		unit_name: string;
		rent_unit_price: string;
		currency: string;
	}
	let tenantLeases: TenantLease[] = [];

	// Outstanding invoices for selected tenant
	let outstandingInvoices: Invoice[] = [];
	let loadingInvoices = false;

	// Invoice selection + allocation amounts
	let selectedInvoiceIds: Set<number> = new Set();
	let allocationAmounts: Record<number, string> = {};

	// Payment form
	let form = {
		amount: '',
		payment_date: new Date().toISOString().split('T')[0],
		payment_method: 'cash',
		reference: '',
		notes: ''
	};

	const paymentMethods = [
		{ value: 'cash', label: 'payments.cash', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z' },
		{ value: 'bank_transfer', label: 'payments.bank_transfer', icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
		{ value: 'mobile_money', label: 'payments.mobile_money', icon: 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z' },
		{ value: 'check', label: 'payments.cheque', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' }
	];

	// Success result
	let successResult: {
		payment: Payment;
		allocations: { invoice_number: string; amount: number; new_status: string }[];
		remaining: number;
	} | null = null;

	// --- Computed ---
	$: {
		const q = tenantSearch.toLowerCase().trim();
		filteredTenants = q.length >= 1
			? tenants.filter((t) => t.display_name.toLowerCase().includes(q))
			: tenants;
	}

	$: totalAllocated = Array.from(selectedInvoiceIds).reduce((sum, id) => {
		return sum + (parseFloat(allocationAmounts[id] || '0') || 0);
	}, 0);

	$: paymentAmount = parseFloat(form.amount) || 0;
	$: unallocatedPreview = paymentAmount - totalAllocated;

	$: {
		// Auto-fill amount to match total allocated
		if (totalAllocated > 0) {
			form.amount = String(totalAllocated);
		}
	}

	$: canSubmit =
		selectedTenant &&
		totalAllocated > 0 &&
		form.payment_date &&
		selectedInvoiceIds.size > 0;

	// Detect the currency from selected invoices (or first lease)
	$: currency = outstandingInvoices.length > 0
		? outstandingInvoices[0].currency
		: tenantLeases.length > 0
			? tenantLeases[0].currency
			: 'XAF';

	// --- Functions ---
	async function load() {
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(page), page_size: '25' });
			const res = await api.payments.list(params.toString());
			payments = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	async function loadTenants() {
		try {
			const res = await api.tenants.list('page_size=1000');
			tenants = res.results;
		} catch {}
	}

	onMount(() => {
		load();
		loadTenants();
	});

	function selectTenant(tenant: Tenant) {
		selectedTenant = tenant;
		tenantSearch = tenant.display_name;
		showTenantDropdown = false;
		selectedInvoiceIds = new Set();
		allocationAmounts = {};
		form.amount = '';
		loadTenantInvoices(tenant.id);
	}

	async function loadTenantInvoices(tenantId: number) {
		loadingInvoices = true;
		outstandingInvoices = [];
		tenantLeases = [];
		try {
			// Fetch active leases for this tenant
			const leaseRes = await api.leases.list(`tenant=${tenantId}&status=active&page_size=100`);
			tenantLeases = leaseRes.results.map((l) => ({
				id: l.id,
				unit_name: l.unit_name,
				rent_unit_price: l.rent_unit_price,
				currency: l.currency
			}));

			// Fetch outstanding invoices (issued + partially_paid) for all tenant leases
			const invoiceRes = await api.invoices.list(
				`tenant=${tenantId}&status=issued&status=partially_paid&ordering=due_date&page_size=100`
			);
			outstandingInvoices = invoiceRes.results;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to load invoices';
		} finally {
			loadingInvoices = false;
		}
	}

	function toggleInvoice(inv: Invoice) {
		const newSet = new Set(selectedInvoiceIds);
		if (newSet.has(inv.id)) {
			newSet.delete(inv.id);
			delete allocationAmounts[inv.id];
			allocationAmounts = allocationAmounts;
		} else {
			newSet.add(inv.id);
			// Default allocation: full balance
			allocationAmounts[inv.id] = inv.balance;
			allocationAmounts = allocationAmounts;
		}
		selectedInvoiceIds = newSet;
	}


	function selectAllInvoices() {
		if (selectedInvoiceIds.size === outstandingInvoices.length) {
			// Deselect all
			selectedInvoiceIds = new Set();
			allocationAmounts = {};
		} else {
			// Select all
			const newSet = new Set<number>();
			const newAmounts: Record<number, string> = {};
			for (const inv of outstandingInvoices) {
				newSet.add(inv.id);
				newAmounts[inv.id] = inv.balance;
			}
			selectedInvoiceIds = newSet;
			allocationAmounts = newAmounts;
		}
	}

	function goToConfirm() {
		saveError = '';
		step = 'confirm';
	}

	async function submitPayment() {
		if (!selectedTenant || !canSubmit) return;
		saving = true;
		saveError = '';

		try {
			// Group selected invoices by lease
			const invoicesByLease: Record<number, { invoice: Invoice; amount: number }[]> = {};
			for (const inv of outstandingInvoices) {
				if (!selectedInvoiceIds.has(inv.id)) continue;
				const amt = parseFloat(allocationAmounts[inv.id] || '0');
				if (amt <= 0) continue;
				if (!invoicesByLease[inv.lease]) invoicesByLease[inv.lease] = [];
				invoicesByLease[inv.lease].push({ invoice: inv, amount: amt });
			}

			const allocations: { invoice_number: string; amount: number; new_status: string }[] = [];
			let totalRemaining = paymentAmount;

			// Create one payment per lease (most tenants have 1 lease)
			for (const [leaseId, items] of Object.entries(invoicesByLease)) {
				const leaseTotal = items.reduce((s, i) => s + i.amount, 0);

				// Create the payment
				const payment = await api.payments.create({
					lease: Number(leaseId),
					amount: leaseTotal,
					currency,
					payment_date: form.payment_date,
					payment_method: form.payment_method,
					reference: form.reference,
					notes: form.notes
				});

				// Allocate to each invoice
				for (const item of items) {
					await api.payments.allocate({
						payment_id: payment.id,
						invoice_id: item.invoice.id,
						amount: item.amount
					});
					const newBalance = parseFloat(item.invoice.balance) - item.amount;
					allocations.push({
						invoice_number: item.invoice.invoice_number,
						amount: item.amount,
						new_status: newBalance <= 0 ? 'paid' : 'partially_paid'
					});
				}

				totalRemaining -= leaseTotal;
			}

			successResult = {
				payment: {} as Payment, // placeholder
				allocations,
				remaining: Math.max(0, totalRemaining)
			};
			step = 'success';
			await load(); // refresh the list in the background
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Payment failed';
			step = 'form';
		} finally {
			saving = false;
		}
	}

	function resetRecorder() {
		step = 'form';
		selectedTenant = null;
		tenantSearch = '';
		outstandingInvoices = [];
		tenantLeases = [];
		selectedInvoiceIds = new Set();
		allocationAmounts = {};
		form = {
			amount: '',
			payment_date: new Date().toISOString().split('T')[0],
			payment_method: 'cash',
			reference: '',
			notes: ''
		};
		saveError = '';
		successResult = null;
	}

	function closeRecorder() {
		showRecorder = false;
		resetRecorder();
	}

	function recordAnother() {
		resetRecorder();
	}

	async function voidPayment(p: Payment) {
		const reason = prompt($t('payments.voidConfirm'));
		if (!reason) return;
		try {
			await api.payments.void(p.id, reason);
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	}

	function daysOverdue(dueDateStr: string): number {
		const due = new Date(dueDateStr);
		const today = new Date();
		const diff = Math.floor((today.getTime() - due.getTime()) / (1000 * 60 * 60 * 24));
		return diff;
	}

	function handleTenantInput() {
		showTenantDropdown = true;
		if (selectedTenant && tenantSearch !== selectedTenant.display_name) {
			selectedTenant = null;
			outstandingInvoices = [];
			tenantLeases = [];
			selectedInvoiceIds = new Set();
			allocationAmounts = {};
		}
	}
</script>

<svelte:head><title>{$t('payments.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('payments.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('payments.subtitle')}</p>
			</div>
			<div class="flex-shrink-0">
				<button
					on:click={() => { showRecorder = true; resetRecorder(); }}
					class="btn-on-dark"
				>+ {$t('payments.addPayment')}</button>
			</div>
		</div>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={payments.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.tenant')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.paymentDate')}</th>
				<th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.amount')}</th>
				<th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">Unallocated</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.method')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.reference')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('payments.status')}</th>
				<th class="px-4 py-3"></th>
			</tr>
		</svelte:fragment>
		{#each payments as p}
			<tr class="hover:bg-gray-50">
				<td class="px-4 py-3 text-gray-900">{p.tenant_name}</td>
				<td class="px-4 py-3 text-gray-600">{formatDate(p.payment_date)}</td>
				<td class="px-4 py-3 text-right font-medium text-gray-900">{formatCurrency(p.amount, p.currency)}</td>
				<td class="px-4 py-3 text-right {Number(p.unallocated_amount) > 0 ? 'text-orange-600' : 'text-gray-400'}">{formatCurrency(p.unallocated_amount, p.currency)}</td>
				<td class="px-4 py-3 capitalize text-gray-600">{p.payment_method.replace('_', ' ')}</td>
				<td class="px-4 py-3 text-xs text-gray-500">{p.reference || '–'}</td>
				<td class="px-4 py-3">
					<Badge variant={PAYMENT_STATUS_COLORS[p.status]} label={p.status} />
				</td>
				<td class="px-4 py-3">
					{#if p.status === 'posted'}
						<button class="text-xs text-red-600 hover:underline" on:click={() => voidPayment(p)}>{$t('payments.voidPayment')}</button>
					{/if}
				</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- ========== RECORD PAYMENT SLIDE-OVER ========== -->
{#if showRecorder}
	<div class="fixed inset-0 z-50 flex justify-end bg-black/40" on:click|self={closeRecorder} role="dialog" aria-modal="true" aria-label={$t('payments.newPayment')}>
		<div class="w-full max-w-2xl bg-white flex flex-col h-full overflow-hidden animate-slide-in">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4 flex-shrink-0">
				<div>
					<h2 class="text-lg font-semibold text-gray-900">{$t('payments.newPayment')}</h2>
					{#if step === 'form'}
						<p class="text-xs text-gray-500 mt-0.5">Select a tenant, choose invoices, and record payment</p>
					{:else if step === 'confirm'}
						<p class="text-xs text-gray-500 mt-0.5">Review and confirm</p>
					{:else}
						<p class="text-xs text-green-600 mt-0.5 font-medium">{$t('payments.created')}</p>
					{/if}
				</div>
				<button type="button" class="p-1.5 text-gray-500 hover:bg-gray-100" on:click={closeRecorder} aria-label={$t('common.close')}>
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<!-- Body -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				{#if step === 'form'}
					<!-- STEP 1: FORM -->
					<div class="space-y-5">
						<!-- Tenant Search -->
						<div>
							<label class="label" for="tenant-search">{$t('payments.tenant')}</label>
							<div class="relative">
								<div class="relative">
									<svg class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
									</svg>
									<input
										id="tenant-search"
										class="input pl-9"
										type="text"
										placeholder={$t('payments.searchPlaceholder')}
										bind:value={tenantSearch}
										on:input={handleTenantInput}
										on:focus={() => (showTenantDropdown = true)}
										autocomplete="off"
									/>
									{#if selectedTenant}
										<button
											class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100"
											on:click={() => { tenantSearch = ''; selectedTenant = null; outstandingInvoices = []; tenantLeases = []; selectedInvoiceIds = new Set(); allocationAmounts = {}; }}
											aria-label={$t('common.close')}
										>
											<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
											</svg>
										</button>
									{/if}
								</div>
								{#if showTenantDropdown && filteredTenants.length > 0 && !selectedTenant}
									<div class="absolute z-10 mt-1 w-full border border-gray-200 bg-white max-h-48 overflow-y-auto">
										{#each filteredTenants as t}
											<button
												class="w-full px-4 py-2.5 text-left text-sm hover:bg-primary-50 flex items-center gap-3 transition-colors"
												on:click={() => selectTenant(t)}
											>
												<span class="flex items-center justify-center w-8 h-8 rounded-full bg-primary-100 text-primary-600 text-xs font-semibold flex-shrink-0">
													{t.display_name.charAt(0).toUpperCase()}
												</span>
												<div>
													<div class="font-medium text-gray-900">{t.display_name}</div>
													{#if t.email}
														<div class="text-xs text-gray-500">{t.email}</div>
													{/if}
												</div>
											</button>
										{/each}
									</div>
								{/if}
							</div>
						</div>

						<!-- Outstanding Invoices -->
						{#if selectedTenant}
							<div>
								<div class="flex items-center justify-between mb-2">
									<label class="label mb-0">Outstanding Invoices</label>
									{#if outstandingInvoices.length > 1}
										<button class="text-xs text-primary-600 hover:text-primary-800 font-medium" on:click={selectAllInvoices}>
											{selectedInvoiceIds.size === outstandingInvoices.length ? 'Deselect All' : 'Select All'}
										</button>
									{/if}
								</div>

								{#if loadingInvoices}
									<div class="flex justify-center py-6"><Spinner /></div>
								{:else if outstandingInvoices.length === 0}
									<div class="border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center">
										<svg class="mx-auto h-8 w-8 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
										<p class="text-sm text-gray-500">{$t('payments.noPayments')}</p>
									</div>
								{:else}
									<div class="space-y-2">
										{#each outstandingInvoices as inv}
											{@const isSelected = selectedInvoiceIds.has(inv.id)}
											{@const overdueDays = daysOverdue(inv.due_date)}
											{@const isOverdue = overdueDays > 0 && inv.status !== 'paid'}
											<button
												class="w-full text-left border-2 p-3 transition-all {isSelected ? 'border-primary-500 bg-primary-50/50' : 'border-gray-200 hover:border-gray-300 bg-white'}"
												on:click={() => toggleInvoice(inv)}
											>
												<div class="flex items-start justify-between gap-3">
													<div class="flex items-start gap-3">
														<!-- Checkbox -->
														<div class="mt-0.5 flex-shrink-0">
															<div class="w-5 h-5 border-2 flex items-center justify-center transition-colors {isSelected ? 'bg-primary-600 border-primary-600' : 'border-gray-300'}">
																{#if isSelected}
																	<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
																	</svg>
																{/if}
															</div>
														</div>
														<div>
															<div class="flex items-center gap-2">
																<span class="text-sm font-semibold text-gray-900">{inv.invoice_number}</span>
																{#if isOverdue}
																	<span class="inline-flex items-center bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">
																		{overdueDays}d overdue
																	</span>
																{:else if inv.status === 'partially_paid'}
																	<span class="inline-flex items-center bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">
																		{$t('status.invoice.partially_paid')}
																	</span>
																{/if}
															</div>
															<div class="text-xs text-gray-500 mt-0.5">
																{inv.unit_name} · Due {formatDate(inv.due_date)}
															</div>
															<div class="text-xs text-gray-400 mt-0.5">
																{inv.period_start} → {inv.period_end}
															</div>
														</div>
													</div>
													<div class="text-right flex-shrink-0">
														<div class="text-sm font-bold text-gray-900">{formatCurrency(inv.balance, inv.currency)}</div>
														{#if inv.status === 'partially_paid'}
															<div class="text-[10px] text-gray-400">of {formatCurrency(inv.total_amount, inv.currency)}</div>
														{/if}
													</div>
												</div>

												<!-- Allocation amount input (show when selected) -->
												{#if isSelected}
													<div class="mt-2.5 pt-2.5 border-t border-primary-200/50">
														<div class="flex items-center gap-2">
															<span class="text-xs text-gray-500 whitespace-nowrap">Allocate:</span>
															<!-- svelte-ignore a11y-click-events-have-key-events -->
															<div class="relative flex-1" on:click|stopPropagation role="textbox" tabindex="-1">
																<input
																	class="input text-sm h-8 pr-14"
																	type="number"
																	step="0.01"
																	min="0.01"
																	max={inv.balance}
																	bind:value={allocationAmounts[inv.id]}
																	on:click|stopPropagation
																/>
																<span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">{inv.currency}</span>
															</div>
															<!-- svelte-ignore a11y-click-events-have-key-events -->
															<span
																class="text-xs text-primary-600 hover:text-primary-800 cursor-pointer font-medium whitespace-nowrap"
																on:click|stopPropagation={() => { allocationAmounts[inv.id] = inv.balance; allocationAmounts = allocationAmounts; }}
																role="button"
																tabindex="0"
															>Full</span>
														</div>
													</div>
												{/if}
											</button>
										{/each}
									</div>
								{/if}
							</div>

							<!-- Payment Details -->
							{#if selectedInvoiceIds.size > 0}
								<div class="border border-gray-200 bg-gray-50 p-4 space-y-3">
									<h3 class="text-xs font-semibold text-gray-700 uppercase tracking-wide">Payment Details</h3>

									<div class="grid grid-cols-2 gap-3">
										<div>
											<label class="label text-xs" for="pay-amount">Total Payment</label>
											<div class="relative">
												<input
													id="pay-amount"
													class="input pr-14 bg-gray-50"
													type="number"
													step="0.01"
													bind:value={form.amount}
													readonly
												/>
												<span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">{currency}</span>
											</div>
											<p class="text-[11px] text-gray-400 mt-1">Auto-calculated from invoice allocations</p>
										</div>
										<div>
											<label class="label text-xs" for="pay-date">{$t('payments.paymentDate')}</label>
											<input id="pay-date" class="input" type="date" bind:value={form.payment_date} required />
										</div>
									</div>

									<div>
										<label class="label text-xs" for="pay-method">{$t('payments.method')}</label>
										<div class="grid grid-cols-4 gap-2">
											{#each paymentMethods as m}
												<button
													type="button"
													class="flex flex-col items-center gap-1 border-2 px-2 py-2.5 text-xs transition-all {form.payment_method === m.value ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium' : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
													on:click={() => (form.payment_method = m.value)}
												>
													<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={m.icon} />
													</svg>
													{$t(m.label)}
												</button>
											{/each}
										</div>
									</div>

									<div class="grid grid-cols-2 gap-3">
										<div>
											<label class="label text-xs" for="pay-ref">{$t('payments.reference')}</label>
											<input id="pay-ref" class="input" bind:value={form.reference} placeholder="Receipt #, txn ID…" />
										</div>
										<div>
											<label class="label text-xs" for="pay-notes">{$t('common.notes')}</label>
											<input id="pay-notes" class="input" bind:value={form.notes} placeholder={$t('common.optional')} />
										</div>
									</div>
								</div>

								<!-- Summary Bar -->
								<div class="bg-primary-600 text-white p-4 flex items-center justify-between">
									<div class="space-y-0.5">
										<div class="text-xs text-primary-200">Payment for {selectedInvoiceIds.size} invoice{selectedInvoiceIds.size > 1 ? 's' : ''}</div>
										<div class="text-2xl font-bold">{formatCurrency(totalAllocated, currency)}</div>
									</div>
									<svg class="h-6 w-6 text-primary-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								</div>
							{/if}
						{/if}
					</div>

				{:else if step === 'confirm'}
					<!-- STEP 2: CONFIRMATION -->
					<div class="space-y-5">
						<div class="border border-primary-200 bg-primary-50 p-4">
							<div class="flex items-center gap-3 mb-3">
								<div class="flex items-center justify-center w-10 h-10 rounded-full bg-primary-100">
									<svg class="h-5 w-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								</div>
								<div>
									<div class="font-semibold text-gray-900">Confirm Payment</div>
									<div class="text-sm text-gray-600">{selectedTenant?.display_name}</div>
								</div>
							</div>

							<div class="space-y-2.5 mt-4">
								{#each outstandingInvoices.filter((inv) => selectedInvoiceIds.has(inv.id)) as inv}
									<div class="flex items-center justify-between bg-white px-3 py-2.5 border border-primary-100">
										<div>
											<span class="text-sm font-medium text-gray-900">{inv.invoice_number}</span>
											<span class="text-xs text-gray-500 ml-2">{inv.unit_name}</span>
										</div>
										<span class="text-sm font-bold text-gray-900">{formatCurrency(allocationAmounts[inv.id] || '0', inv.currency)}</span>
									</div>
								{/each}
							</div>

							<div class="mt-4 pt-3 border-t border-primary-200 flex items-center justify-between">
								<span class="text-sm font-medium text-gray-700">Total</span>
								<span class="text-lg font-bold text-primary-700">{formatCurrency(totalAllocated, currency)}</span>
							</div>
						</div>

						<div class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<div class="text-gray-500">{$t('payments.paymentDate')}</div>
							<div class="font-medium text-gray-900">{formatDate(form.payment_date)}</div>
							<div class="text-gray-500">{$t('payments.method')}</div>
							<div class="font-medium text-gray-900 capitalize">{form.payment_method.replace('_', ' ')}</div>
							{#if form.reference}
								<div class="text-gray-500">{$t('payments.reference')}</div>
								<div class="font-medium text-gray-900">{form.reference}</div>
							{/if}
							{#if form.notes}
								<div class="text-gray-500">{$t('common.notes')}</div>
								<div class="font-medium text-gray-900">{form.notes}</div>
							{/if}
						</div>

						{#if saveError}
							<div class="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{saveError}</div>
						{/if}
					</div>

				{:else if step === 'success'}
					<!-- STEP 3: SUCCESS -->
					<div class="flex flex-col items-center text-center py-6">
						<div class="flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
							<svg class="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
							</svg>
						</div>
						<h3 class="text-xl font-bold text-gray-900 mb-1">{$t('payments.created')}</h3>
						<p class="text-sm text-gray-500 mb-6">{selectedTenant?.display_name}</p>

						{#if successResult}
							<div class="w-full space-y-2 mb-6">
								{#each successResult.allocations as alloc}
									<div class="flex items-center justify-between bg-gray-50 border border-gray-200 px-4 py-3">
										<div class="text-left">
											<span class="text-sm font-medium text-gray-900">{alloc.invoice_number}</span>
											<span class="ml-2">
												{#if alloc.new_status === 'paid'}
													<span class="inline-flex items-center bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700">{$t('status.invoice.paid')}</span>
												{:else}
													<span class="inline-flex items-center bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">{$t('status.invoice.partially_paid')}</span>
												{/if}
											</span>
										</div>
										<span class="text-sm font-bold text-gray-900">{formatCurrency(alloc.amount, currency)}</span>
									</div>
								{/each}
							</div>

							{#if successResult.remaining > 0.01}
								<div class="w-full bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800 mb-6">
									{formatCurrency(successResult.remaining, currency)} remains unallocated
								</div>
							{/if}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="border-t border-gray-200 px-6 py-4 flex-shrink-0">
				{#if step === 'form'}
					<div class="flex justify-end gap-3">
						<button class="btn-secondary" on:click={closeRecorder}>{$t('common.cancel')}</button>
						<button
							class="btn-primary"
							disabled={!canSubmit}
							on:click={goToConfirm}
						>
							Review Payment
						</button>
					</div>
				{:else if step === 'confirm'}
					<div class="flex justify-between">
						<button class="btn-secondary" on:click={() => (step = 'form')}>
							Back
						</button>
						<button
							class="btn-primary"
							disabled={saving}
							on:click={submitPayment}
						>
							{#if saving}
								<span class="inline-flex items-center gap-2">
									<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
									{$t('common.saving')}
								</span>
							{:else}
								Confirm & Record
							{/if}
						</button>
					</div>
				{:else}
					<div class="flex justify-between">
						<button class="btn-secondary" on:click={recordAnother}>Record Another</button>
						<button class="btn-primary" on:click={closeRecorder}>{$t('common.close')}</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	@keyframes slideIn {
		from { transform: translateX(100%); }
		to { transform: translateX(0); }
	}
	.animate-slide-in {
		animation: slideIn 0.25s ease-out;
	}
</style>

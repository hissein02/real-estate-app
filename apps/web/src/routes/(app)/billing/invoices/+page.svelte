<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api, getAccessToken, downloadWithAuth } from '$lib/api/client';
	import type { Invoice } from '$lib/api/types';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import { INVOICE_STATUS_COLORS } from '$lib/utils/status';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Modal from '$lib/components/Modal.svelte';

	let invoices: Invoice[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';
	let statusFilter = '';
	let search = '';
	let exporting = '';

	async function runExport(url: string, name: string) {
		exporting = name;
		error = '';
		try {
			await downloadWithAuth(url, name);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Export failed';
		} finally {
			exporting = '';
		}
	}
	let tenantFilter = '';
	let tenants: { id: number; display_name: string }[] = [];
	let searchTimer: ReturnType<typeof setTimeout>;

	// Debounced: the list reloads on every keystroke otherwise.
	function onSearch() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			page = 1;
			load();
		}, 300);
	}
	// Document viewer
	let viewModal = false;
	let viewTarget: Invoice | null = null;
	let viewHtml = '';
	let viewLoading = false;
	let pdfLoading = false;

	async function openView(inv: Invoice) {
		viewTarget = inv;
		viewHtml = '';
		viewModal = true;
		viewLoading = true;
		try {
			const res = await api.invoices.preview(inv.id);
			viewHtml = res.html;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
			viewModal = false;
		} finally {
			viewLoading = false;
		}
	}

	async function downloadPdf(inv: Invoice) {
		pdfLoading = true;
		try {
			const token = getAccessToken();
			const res = await fetch(api.invoices.pdfUrl(inv.id), {
				headers: token ? { Authorization: `Bearer ${token}` } : {}
			});
			if (!res.ok) throw new Error('PDF');
			const url = URL.createObjectURL(await res.blob());
			const a = document.createElement('a');
			a.href = url;
			a.download = `${inv.invoice_number}.pdf`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			pdfLoading = false;
		}
	}

	let voidModal = false;
	let voidTarget: Invoice | null = null;
	let voidReason = '';
	let voiding = false;

	// Date editing
	let datesModal = false;
	let datesTarget: Invoice | null = null;
	let datesInvoiceDate = '';
	let datesDueDate = '';
	let datesReason = '';
	let datesSaving = false;
	let datesWarnings: string[] = [];

	function openDates(inv: Invoice) {
		datesTarget = inv;
		datesInvoiceDate = inv.invoice_date ?? '';
		datesDueDate = inv.due_date;
		datesReason = '';
		datesWarnings = [];
		datesModal = true;
	}

	async function load() {
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(page), page_size: '25' });
			if (statusFilter) params.set('status', statusFilter);
			if (search.trim()) params.set('search', search.trim());
			if (tenantFilter) params.set('tenant', tenantFilter);
			const res = await api.invoices.list(params.toString());
			invoices = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	onMount(async () => {
		await load();
		try {
			const res = await api.tenants.list('page_size=500&ordering=last_name');
			tenants = res.results.map((t) => ({ id: t.id, display_name: t.display_name }));
		} catch {
			// The tenant filter is a convenience; the list still works without it.
		}
	});

	async function confirmDates() {
		if (!datesTarget) return;
		datesSaving = true;
		error = '';
		try {
			const payload: { invoice_date?: string; due_date?: string; reason?: string } = {};
			if (datesInvoiceDate) payload.invoice_date = datesInvoiceDate;
			if (datesDueDate) payload.due_date = datesDueDate;
			if (datesReason.trim()) payload.reason = datesReason.trim();
			const updated = await api.invoices.setDates(datesTarget.id, payload);
			datesWarnings = updated.warnings ?? [];
			await load();
			// Keep the dialog open when there is something to read.
			if (datesWarnings.length === 0) datesModal = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
			datesModal = false;
		} finally {
			datesSaving = false;
		}
	}

	async function confirmVoid() {
		if (!voidTarget || !voidReason) return;
		voiding = true;
		try {
			await api.invoices.void(voidTarget.id, voidReason);
			voidModal = false;
			voidTarget = null;
			voidReason = '';
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Void failed';
		} finally {
			voiding = false;
		}
	}
</script>

<svelte:head><title>{$t('invoices.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('invoices.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('invoices.subtitle')}</p>
			</div>
			<div class="flex flex-shrink-0 gap-2">
				{#each [
					{ label: $t('invoices.exportCsv'), url: api.reports.exportInvoices('csv'), name: 'invoices.csv' },
					{ label: $t('invoices.exportXlsx'), url: api.reports.exportInvoices('xlsx'), name: 'invoices.xlsx' }
				] as item}
					<button
						class="inline-flex items-center gap-2 border px-4 py-2 text-sm font-medium transition-colors hover:brightness-110 disabled:opacity-60"
						style="background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.15); color: #c8e0f4;"
						disabled={exporting === item.name}
						on:click={() => runExport(item.url, item.name)}
					>{exporting === item.name ? $t('common.loading') : item.label}</button>
				{/each}
			</div>
		</div>
	</div>

	<!-- Controls -->
	<div class="flex flex-wrap items-center gap-3">
		<input
			class="input w-72"
			type="search"
			bind:value={search}
			on:input={onSearch}
			placeholder={$t('invoices.searchPlaceholder')}
			aria-label={$t('invoices.searchPlaceholder')}
		/>
		<select
			class="input w-56"
			bind:value={tenantFilter}
			on:change={() => { page = 1; load(); }}
			aria-label={$t('invoices.allTenants')}
		>
			<option value="">{$t('invoices.allTenants')}</option>
			{#each tenants as t}
				<option value={String(t.id)}>{t.display_name}</option>
			{/each}
		</select>
		<select
			class="input w-44"
			bind:value={statusFilter}
			on:change={() => { page = 1; load(); }}
		>
			<option value="">{$t('invoices.allStatuses')}</option>
			<option value="issued">{$t('status.invoice.issued')}</option>
			<option value="partially_paid">{$t('status.invoice.partially_paid')}</option>
			<option value="paid">{$t('status.invoice.paid')}</option>
			<option value="void">{$t('status.invoice.void')}</option>
		</select>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={invoices.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.invoiceNumber')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.tenant')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.generatedOn')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.dueDate')}</th
				>
				<th
					class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.amount')}</th
				>
				<th
					class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.balance')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.status')}</th
				>
				<th class="px-4 py-3"></th>
			</tr>
		</svelte:fragment>
		{#each invoices as inv}
			<tr class="hover:bg-gray-50 {inv.is_overdue ? 'bg-red-50' : ''}">
				<td class="px-4 py-3 font-mono text-xs text-gray-700">{inv.invoice_number}</td>
				<td class="px-4 py-3 text-gray-900">{inv.tenant_name}</td>
				<td class="px-4 py-3 text-gray-600"
					>{formatDate(inv.invoice_date ?? inv.created_at)}</td
				>
				<td
					class="px-4 py-3 text-gray-600 {inv.is_overdue ? 'font-medium text-red-600' : ''}"
					>{formatDate(inv.due_date)}</td
				>
				<td class="px-4 py-3 text-right text-gray-900">{formatCurrency(inv.total_amount, inv.currency)}</td>
				<td
					class="px-4 py-3 text-right {Number(inv.balance) > 0 ? 'font-medium text-red-600' : 'text-gray-600'}">{formatCurrency(inv.balance, inv.currency)}</td
				>
				<td class="px-4 py-3">
					<Badge
						variant={INVOICE_STATUS_COLORS[inv.status]}
						label={$t('status.invoice.' + inv.status)}
					/>
				</td>
				<td class="px-4 py-3">
					<div class="flex justify-end gap-3 whitespace-nowrap">
						<button class="text-xs text-gray-600 hover:underline" on:click={() => openView(inv)}>
							{$t('invoices.view')}
						</button>
						{#if inv.status !== 'void'}
							<button class="text-xs text-gray-600 hover:underline" on:click={() => openDates(inv)}>
								{$t('invoices.editDates')}
							</button>
						{/if}
						{#if inv.status !== 'void' && inv.status !== 'paid' && Number(inv.paid_amount) === 0}
							<button
								class="text-xs text-red-600 hover:underline"
								on:click={() => {
									voidTarget = inv;
									voidModal = true;
								}}>{$t('invoices.voidInvoice')}</button
							>
						{/if}
					</div>
				</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination
		{count}
		{page}
		on:change={(e) => {
			page = e.detail;
			load();
		}}
	/>
</div>

<Modal bind:open={voidModal} title={$t('invoices.voidInvoice')} on:close={() => (voidModal = false)}>
	<p class="mb-3 text-sm text-gray-600">
		{$t('invoices.voidConfirm')} <strong>{voidTarget?.invoice_number}</strong>
	</p>
	<label class="label" for="void-reason">{$t('invoices.voidReason')}</label>
	<textarea
		id="void-reason"
		class="input"
		rows="3"
		bind:value={voidReason}
		placeholder={$t('invoices.voidReasonPlaceholder')}
	/>
	<svelte:fragment slot="footer">
		<div class="flex justify-end gap-3">
			<button class="btn-secondary" on:click={() => (voidModal = false)}>{$t('common.cancel')}</button>
			<button class="btn-danger" on:click={confirmVoid} disabled={voiding || !voidReason}>
				{voiding ? $t('common.saving') : $t('invoices.voidInvoice')}
			</button>
		</div>
	</svelte:fragment>
</Modal>

<Modal bind:open={datesModal} title={$t('invoices.editDates')} on:close={() => (datesModal = false)}>
	<p class="mb-3 text-xs text-gray-500">{$t('invoices.datesEffects')}</p>
	<div class="grid grid-cols-2 gap-3">
		<div>
			<label class="label" for="d-invoice">{$t('invoices.invoiceDate')}</label>
			<input id="d-invoice" class="input" type="date" bind:value={datesInvoiceDate} />
		</div>
		<div>
			<label class="label" for="d-due">{$t('invoices.dueDate')}</label>
			<input id="d-due" class="input" type="date" bind:value={datesDueDate} />
		</div>
	</div>
	<div class="mt-3">
		<label class="label" for="d-reason">{$t('invoices.datesReason')}</label>
		<input id="d-reason" class="input" type="text" bind:value={datesReason} />
	</div>
	{#if datesWarnings.length > 0}
		<ul class="mt-3 border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
			{#each datesWarnings as w}
				<li class="mb-1 last:mb-0">{w}</li>
			{/each}
		</ul>
	{/if}
	<svelte:fragment slot="footer">
		<div class="action-bar">
			<button class="btn-secondary" on:click={() => (datesModal = false)}>
				{datesWarnings.length > 0 ? $t('common.close') : $t('common.cancel')}
			</button>
			<button class="btn-primary" on:click={confirmDates} disabled={datesSaving || !datesDueDate}>
				{datesSaving ? $t('common.saving') : $t('common.save')}
			</button>
		</div>
	</svelte:fragment>
</Modal>

<Modal
	bind:open={viewModal}
	maxWidth="4xl"
	title={`${$t('invoices.viewInvoice')} ${viewTarget?.invoice_number ?? ''}`}
	on:close={() => (viewModal = false)}
>
	{#if viewLoading}
		<p class="py-16 text-center text-sm text-gray-500">{$t('common.loading')}</p>
	{:else}
		<!-- The document is rendered from the same template as the PDF. It goes in
		     an iframe so its own stylesheet cannot leak into the application. -->
		<div class="overflow-auto bg-gray-100 p-3" style="max-height: 68vh;">
			<iframe
				title={viewTarget?.invoice_number ?? 'invoice'}
				srcdoc={viewHtml}
				style="width: 794px; height: 1123px; border: 0; background: #fff; display: block; margin: 0 auto;"
			></iframe>
		</div>
	{/if}
	<svelte:fragment slot="footer">
		<div class="action-bar">
			<button class="btn-secondary" on:click={() => (viewModal = false)}>{$t('common.close')}</button>
			<button
				class="btn-primary"
				disabled={pdfLoading || !viewTarget}
				on:click={() => viewTarget && downloadPdf(viewTarget)}
			>
				{pdfLoading ? $t('common.loading') : $t('invoices.downloadPdf')}
			</button>
		</div>
	</svelte:fragment>
</Modal>

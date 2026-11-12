<script lang="ts">
	let exporting = '';
	let exportError = '';

	async function runExport(url: string, name: string) {
		exporting = name;
		exportError = '';
		try {
			await downloadWithAuth(url, name);
		} catch (e) {
			exportError = e instanceof Error ? e.message : 'Export failed';
		} finally {
			exporting = '';
		}
	}

	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api, downloadWithAuth } from '$lib/api/client';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import type { ArrearsItem } from '$lib/api/types';
	import DataTable from '$lib/components/DataTable.svelte';

	let loading = true;
	let error = '';
	let totalOverdue = '0';
	let overdueCount = 0;
	let items: ArrearsItem[] = [];

	onMount(async () => {
		try {
			const data = await api.reports.arrears();
			items = data.items;
			totalOverdue = data.total_overdue_amount;
			overdueCount = data.overdue_invoice_count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head><title>{$t('reports.title')} – RealEstate</title></svelte:head>

<div class="space-y-5">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('reports.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('reports.subtitle')}</p>
			</div>
			<div class="flex flex-wrap items-center gap-2 flex-shrink-0">
				{#each [
					{ key: 'exportInvoicesCsv', url: api.reports.exportInvoices('csv'), name: 'invoices.csv' },
					{ key: 'exportInvoicesXlsx', url: api.reports.exportInvoices('xlsx'), name: 'invoices.xlsx' },
					{ key: 'exportPaymentsCsv', url: api.reports.exportPayments('csv'), name: 'payments.csv' },
					{ key: 'exportPaymentsXlsx', url: api.reports.exportPayments('xlsx'), name: 'payments.xlsx' }
				] as item}
					<button
						class="inline-flex items-center gap-2 border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-60"
						style="background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.15); color: #c8e0f4;"
						disabled={exporting === item.name}
						on:click={() => runExport(item.url, item.name)}
					>{exporting === item.name ? $t('common.loading') : $t(`reports.${item.key}`)}</button>
				{/each}
			</div>
		</div>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}
	{#if exportError}<div class="text-sm text-red-600">{exportError}</div>{/if}

	<!-- KPI cards -->
	<div class="grid grid-cols-2 gap-4">
		<div class="border border-gray-100 bg-white p-5" style="border-top: 3px solid #dc2626">
			<p class="text-xs font-semibold uppercase tracking-wide text-gray-400">{$t('reports.overdueInvoices')}</p>
			<p class="mt-2 text-3xl font-bold text-gray-900">{overdueCount}</p>
		</div>
		<div class="border border-gray-100 bg-white p-5" style="border-top: 3px solid #dc2626">
			<p class="text-xs font-semibold uppercase tracking-wide text-gray-400">{$t('reports.overdueAmount')}</p>
			<p class="mt-2 text-3xl font-bold text-gray-900">{formatCurrency(totalOverdue, 'XAF')}</p>
		</div>
	</div>

	<!-- Arrears table -->
	<DataTable {loading} empty={items.length === 0} emptyMessage={$t('table.noData')}>
		<svelte:fragment slot="head">
			<tr>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.invoiceNumber')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('leases.tenant')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('leases.unit')}</th
				>
				<th
					class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('invoices.dueDate')}</th
				>
				<th
					class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('dashboard.overdue')}</th
				>
				<th
					class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500"
					>{$t('common.balance')}</th
				>
			</tr>
		</svelte:fragment>
		{#each items as item}
			<tr class="hover:bg-gray-50">
				<td class="px-4 py-3 font-mono text-xs text-gray-700">{item.invoice_number}</td>
				<td class="px-4 py-3 text-gray-900">{item.tenant}</td>
				<td class="px-4 py-3 text-gray-600">{item.unit}</td>
				<td class="px-4 py-3 text-red-600">{formatDate(item.due_date)}</td>
				<td class="px-4 py-3 text-right font-medium text-red-600">{item.days_overdue}d</td>
				<td class="px-4 py-3 text-right font-bold text-red-700"
					>{formatCurrency(item.balance, item.currency)}</td
				>
			</tr>
		{/each}
	</DataTable>
</div>

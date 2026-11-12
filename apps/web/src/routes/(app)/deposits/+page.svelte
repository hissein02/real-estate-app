<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api } from '$lib/api/client';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';

	interface Deposit {
		id: number;
		lease: number;
		tenant_name?: string;
		unit_name?: string;
		amount: string;
		currency: string;
		status: string;
		received_date?: string;
		refunded_date?: string;
	}

	let deposits: Deposit[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';

	async function load() {
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(page), page_size: '25' });
			const res = await api.deposits.list(params.toString()) as { count: number; results: Deposit[] };
			deposits = res.results ?? [];
			count = res.count ?? deposits.length;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<svelte:head><title>{$t('deposits.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<h1 class="text-2xl font-bold text-white">{$t('deposits.title')}</h1>
		<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('deposits.subtitle')}</p>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={deposits.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Lease ID</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.tenant')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.unit')}</th>
				<th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.amount')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.status')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.depositDate')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('deposits.returnDate')}</th>
			</tr>
		</svelte:fragment>
		{#each deposits as d}
			<tr class="hover:bg-gray-50">
				<td class="px-4 py-3 text-gray-600">{d.lease}</td>
				<td class="px-4 py-3 text-gray-900">{d.tenant_name ?? '–'}</td>
				<td class="px-4 py-3 text-gray-600">{d.unit_name ?? '–'}</td>
				<td class="px-4 py-3 text-right font-medium text-gray-900">{formatCurrency(d.amount, d.currency)}</td>
				<td class="px-4 py-3 text-gray-600">{$t('status.deposit.' + d.status)}</td>
				<td class="px-4 py-3 text-gray-600">{formatDate(d.received_date)}</td>
				<td class="px-4 py-3 text-gray-600">{d.refunded_date ? formatDate(d.refunded_date) : '–'}</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

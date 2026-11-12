<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api } from '$lib/api/client';
	import type { Lease, Unit, Tenant } from '$lib/api/types';
	import { formatCurrency, formatDate } from '$lib/utils/format';
	import { LEASE_STATUS_COLORS, LEASE_STATUS_LABELS } from '$lib/utils/status';
	import { currentUser } from '$lib/stores/auth';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Drawer from '$lib/components/Drawer.svelte';

	let leases: Lease[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';
	let statusFilter = '';

	let unitOptions: Unit[] = [];
	let tenantOptions: Tenant[] = [];

	$: availableUnits = unitOptions.filter((u) => !u.is_occupied);

	$: canEdit = $currentUser?.role === 'admin' || $currentUser?.role === 'manager';
	// Mirrors the API: delete and lease-lifecycle actions are admin/manager only.
	$: canDelete = $currentUser?.role === 'admin' || $currentUser?.role === 'manager';

	// Rent is a unit price per month; a period bills that times the interval.
	$: newPeriodTotal =
		(Number(form.rent_unit_price) || 0) * (Number(form.billing_interval_months) || 1);
	$: editPeriodTotal =
		(Number(editForm.rent_unit_price) || 0) * (Number(editLease?.billing_interval_months) || 1);

	// New lease modal
	let showModal = false;
	let saving = false;
	let form = {
		unit: '',
		tenant: '',
		start_date: '',
		end_date: '',
		rent_unit_price: '',
		currency: 'XAF',
		billing_interval_months: 1,
		billing_cycle_anchor: 'lease_start',
		prorate_first_period: false,
		deposit_amount: '0',
		late_fee_type: 'none',
		late_fee_value: '0',
		late_fee_grace_period_days: 5
	};

	// Edit drawer
	let showDrawer = false;
	let editLease: Lease | null = null;
	let editForm = {
		end_date: '',
		rent_unit_price: '',
		deposit_amount: '',
		late_fee_type: 'none',
		late_fee_value: '0',
		late_fee_grace_period_days: 5,
		notes: ''
	};
	let editSaving = false;

	// Terminate confirm
	let showTerminateConfirm = false;
	let terminationDate = '';
	let terminationReason = '';
	let terminating = false;

	// Delete confirm
	let showDeleteConfirm = false;
	let deleting = false;

	// Cascading delete (admin only) — offered when a plain delete is refused
	$: canForceDelete = $currentUser?.role === 'admin';
	let forcePlan: { will_delete: Record<string, number>; total: number } | null = null;
	let forceDeleting = false;

	/** 'invoice' + 3 -> '3 invoices'; uses the locale's own plural forms. */
	function entityLabel(key: string, n: number): string {
		const base = key.replace(/ /g, '_');
		return `${n} ${$t(`entities.${base}_${n === 1 ? 'one' : 'other'}`)}`;
	}

	async function load() {
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(page), page_size: '25' });
			if (statusFilter) params.set('status', statusFilter);
			const res = await api.leases.list(params.toString());
			leases = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	async function loadDropdowns() {
		try {
			const [unitsRes, tenantsRes] = await Promise.all([
				api.units.list('page_size=1000'),
				api.tenants.list('page_size=1000')
			]);
			unitOptions = unitsRes.results;
			tenantOptions = tenantsRes.results;
		} catch {}
	}

	onMount(() => { load(); loadDropdowns(); });

	async function save() {
		saving = true;
		try {
			await api.leases.create({
				...form,
				unit: Number(form.unit),
				tenant: Number(form.tenant),
				rent_unit_price: Number(form.rent_unit_price),
				deposit_amount: Number(form.deposit_amount),
				late_fee_value: Number(form.late_fee_value),
				end_date: form.end_date || null
			});
			showModal = false;
			form = {
				unit: '', tenant: '', start_date: '', end_date: '',
				rent_unit_price: '', currency: 'XAF', billing_interval_months: 1,
				billing_cycle_anchor: 'lease_start', prorate_first_period: false,
				deposit_amount: '0', late_fee_type: 'none', late_fee_value: '0',
				late_fee_grace_period_days: 5
			};
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			saving = false;
		}
	}

	function openDrawer(lease: Lease) {
		editLease = lease;
		editForm = {
			end_date: lease.end_date ?? '',
			rent_unit_price: lease.rent_unit_price,
			deposit_amount: lease.deposit_amount,
			late_fee_type: lease.late_fee_type,
			late_fee_value: lease.late_fee_value,
			late_fee_grace_period_days: lease.late_fee_grace_period_days,
			notes: lease.notes ?? ''
		};
		showTerminateConfirm = false;
		showDeleteConfirm = false;
		forcePlan = null;
		terminationDate = new Date().toISOString().slice(0, 10);
		terminationReason = '';
		showDrawer = true;
	}

	async function activate() {
		if (!editLease) return;
		try {
			await api.leases.activate(editLease.id);
			showDrawer = false;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		}
	}

	async function saveEdit() {
		if (!editLease) return;
		editSaving = true;
		try {
			await api.leases.update(editLease.id, {
				end_date: editForm.end_date || null,
				rent_unit_price: Number(editForm.rent_unit_price),
				deposit_amount: Number(editForm.deposit_amount),
				late_fee_type: editForm.late_fee_type,
				late_fee_value: Number(editForm.late_fee_value),
				late_fee_grace_period_days: editForm.late_fee_grace_period_days,
				notes: editForm.notes
			});
			showDrawer = false;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			editSaving = false;
		}
	}

	async function confirmTerminate() {
		if (!editLease) return;
		terminating = true;
		try {
			await api.leases.terminate(editLease.id, {
				termination_date: terminationDate,
				reason: terminationReason.trim()
			});
			showDrawer = false;
			showTerminateConfirm = false;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			terminating = false;
		}
	}

	async function confirmDelete() {
		if (!editLease) return;
		deleting = true;
		error = '';
		try {
			await api.leases.delete(editLease.id);
			showDrawer = false;
			showDeleteConfirm = false;
			await load();
		} catch (e) {
			// A 409 carries a message naming exactly what still references the lease.
			error = e instanceof Error ? e.message : 'Error';
			const conflict = (e as { data?: { blocked_by?: unknown } })?.data?.blocked_by;
			showDeleteConfirm = false;
			// Offer the cascade only when the refusal was a reference conflict.
			if (conflict && canForceDelete && editLease) {
				try {
					forcePlan = await api.leases.deletionPreview(editLease.id);
				} catch {
					forcePlan = null;
				}
			}
		} finally {
			deleting = false;
		}
	}

	async function confirmForceDelete() {
		if (!editLease) return;
		forceDeleting = true;
		error = '';
		try {
			await api.leases.forceDelete(editLease.id);
			showDrawer = false;
			forcePlan = null;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			forceDeleting = false;
		}
	}
</script>

<svelte:head><title>{$t('leases.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('leases.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('leases.subtitle')}</p>
			</div>
			<div class="flex-shrink-0">
				<button
					on:click={() => (showModal = true)}
					class="btn-on-dark"
				>+ {$t('leases.addLease')}</button>
			</div>
		</div>
	</div>

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<select
			class="input w-40"
			bind:value={statusFilter}
			on:change={() => { page = 1; load(); }}
		>
			<option value="">{$t('leases.status')}</option>
			<option value="draft">{$t('status.lease.draft')}</option>
			<option value="active">{$t('status.lease.active')}</option>
			<option value="expired">{$t('status.lease.expired')}</option>
			<option value="terminated">{$t('status.lease.terminated')}</option>
		</select>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={leases.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.tenant')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.unit')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.startDate')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.endDate')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.rentAmount')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('leases.status')}</th>
			</tr>
		</svelte:fragment>
		{#each leases as l}
			<tr class="cursor-pointer hover:bg-gray-50" on:click={() => openDrawer(l)}>
				<td class="px-4 py-3 font-medium text-gray-900">{l.tenant_name}</td>
				<td class="px-4 py-3 text-gray-600">{l.unit_name}</td>
				<td class="px-4 py-3 text-gray-600">{formatDate(l.start_date)}</td>
				<td class="px-4 py-3 text-gray-600">{l.end_date ? formatDate(l.end_date) : '–'}</td>
				<td class="px-4 py-3 text-gray-600">{formatCurrency(l.rent_unit_price, l.currency)}</td>
				<td class="px-4 py-3">
					<Badge variant={LEASE_STATUS_COLORS[l.status]} label={LEASE_STATUS_LABELS[l.status]} />
				</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- New Lease modal -->
<Modal bind:open={showModal} title={$t('leases.newLease')} maxWidth="lg" on:close={() => (showModal = false)}>
	<form on:submit|preventDefault={save} class="space-y-4">
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="l-unit">{$t('leases.unit')}</label>
				<select id="l-unit" class="input" bind:value={form.unit} required>
					<option value="" disabled>{$t('leases.selectUnit')}</option>
					{#each availableUnits as u}
						<option value={u.id}>{u.name} ({u.property_name})</option>
					{/each}
				</select>
			</div>
			<div>
				<label class="label" for="l-tenant">{$t('leases.tenant')}</label>
				<select id="l-tenant" class="input" bind:value={form.tenant} required>
					<option value="" disabled>{$t('leases.selectTenant')}</option>
					{#each tenantOptions as t}
						<option value={t.id}>{t.display_name}</option>
					{/each}
				</select>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="l-start">{$t('leases.startDate')}</label>
				<input id="l-start" class="input" type="date" bind:value={form.start_date} required />
			</div>
			<div>
				<label class="label" for="l-end">{$t('leases.endDate')} ({$t('common.optional')})</label>
				<input id="l-end" class="input" type="date" bind:value={form.end_date} />
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="l-rent">{$t('leases.rentAmount')}</label>
				<input id="l-rent" class="input" type="number" step="0.01" bind:value={form.rent_unit_price} required />
				{#if newPeriodTotal > 0 && Number(form.billing_interval_months) > 1}
					<p class="mt-1 text-xs text-gray-500">
						{$t('leases.rentPeriodTotal')}: {form.billing_interval_months} ×
						{formatCurrency(String(form.rent_unit_price), form.currency)} =
						{formatCurrency(String(newPeriodTotal), form.currency)}
					</p>
				{/if}
			</div>
			<div>
				<label class="label" for="l-currency">{$t('leases.currency')}</label>
				<select id="l-currency" class="input" bind:value={form.currency}>
					<option value="XAF">XAF</option>
					<option value="EUR">EUR</option>
					<option value="USD">USD</option>
				</select>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="l-interval">{$t('leases.billingInterval')}</label>
				<input id="l-interval" class="input" type="number" min="1" bind:value={form.billing_interval_months} />
			</div>
			<div>
				<label class="label" for="l-anchor">{$t('leases.billingAnchor')}</label>
				<select id="l-anchor" class="input" bind:value={form.billing_cycle_anchor}>
					<option value="lease_start">{$t('leases.leaseStart')}</option>
					<option value="month_start">{$t('leases.monthStart')}</option>
				</select>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="l-deposit">{$t('leases.depositAmount')}</label>
				<input id="l-deposit" class="input" type="number" step="0.01" bind:value={form.deposit_amount} />
			</div>
			<div>
				<label class="label" for="l-late-type">{$t('leases.lateFeeType')}</label>
				<select id="l-late-type" class="input" bind:value={form.late_fee_type}>
					<option value="none">{$t('leases.none')}</option>
					<option value="fixed">{$t('leases.fixed')}</option>
					<option value="percentage">{$t('leases.percentage')}</option>
				</select>
			</div>
		</div>
		{#if form.late_fee_type !== 'none'}
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="label" for="l-late-val">{$t('leases.lateFeeValue')}</label>
					<input id="l-late-val" class="input" type="number" step="0.01" bind:value={form.late_fee_value} />
				</div>
				<div>
					<label class="label" for="l-grace">{$t('leases.gracePeriodDays')}</label>
					<input id="l-grace" class="input" type="number" bind:value={form.late_fee_grace_period_days} />
				</div>
			</div>
		{/if}
		<div class="flex items-center gap-2">
			<input id="l-prorate" type="checkbox" bind:checked={form.prorate_first_period} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="l-prorate" class="text-sm text-gray-700">Prorate first period</label>
		</div>
	</form>
	<svelte:fragment slot="footer">
		<div class="flex justify-end gap-3">
			<button class="btn-secondary" on:click={() => (showModal = false)}>{$t('common.cancel')}</button>
			<button class="btn-primary" on:click={save} disabled={saving}>{saving ? $t('common.saving') : $t('leases.newLease')}</button>
		</div>
	</svelte:fragment>
</Modal>

<!-- Edit / View drawer -->
<Drawer
	bind:open={showDrawer}
	title={canEdit ? $t('leases.editLease') : $t('leases.title')}
	subtitle={editLease ? `${editLease.tenant_name} · ${editLease.unit_name}` : ''}
	on:close={() => (showDrawer = false)}
>
	{#if editLease}
		<!-- Info summary -->
		<div class="mb-5 grid grid-cols-2 gap-3">
			<div class="border border-gray-100 bg-gray-50 p-3">
				<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('leases.status')}</p>
				<div class="mt-1.5">
					<Badge variant={LEASE_STATUS_COLORS[editLease.status]} label={LEASE_STATUS_LABELS[editLease.status]} />
				</div>
			</div>
			<div class="border border-gray-100 bg-gray-50 p-3">
				<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('leases.rentAmount')}</p>
				<p class="mt-1 text-base font-bold text-gray-900">{formatCurrency(editLease.rent_unit_price, editLease.currency)}</p>
			</div>
			<div class="border border-gray-100 bg-gray-50 p-3">
				<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('leases.startDate')}</p>
				<p class="mt-1 text-sm font-medium text-gray-900">{formatDate(editLease.start_date)}</p>
			</div>
			<div class="border border-gray-100 bg-gray-50 p-3">
				<p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{$t('leases.endDate')}</p>
				<p class="mt-1 text-sm font-medium text-gray-900">{editLease.end_date ? formatDate(editLease.end_date) : '–'}</p>
			</div>
		</div>

		{#if !canEdit}
			<p class="mb-4 bg-amber-50 px-3 py-2 text-xs text-amber-700">
				{$t('leases.readOnlyNotice')}
			</p>
		{/if}

		<!-- Editable fields -->
		<div class="space-y-4">
			<div>
				<label class="label" for="el-end">{$t('leases.endDate')} ({$t('common.optional')})</label>
				<input id="el-end" class="input" type="date" bind:value={editForm.end_date} disabled={!canEdit} />
			</div>
			<div>
				<label class="label" for="el-rent">{$t('leases.rentAmount')}</label>
				<input id="el-rent" class="input" type="number" step="0.01" bind:value={editForm.rent_unit_price} disabled={!canEdit} />
				{#if editPeriodTotal > 0 && Number(editLease?.billing_interval_months) > 1}
					<p class="mt-1 text-xs text-gray-500">
						{$t('leases.rentPeriodTotal')}: {editLease?.billing_interval_months} ×
						{formatCurrency(String(editForm.rent_unit_price), editLease?.currency ?? 'XAF')} =
						{formatCurrency(String(editPeriodTotal), editLease?.currency ?? 'XAF')}
					</p>
				{/if}
			</div>
			<div>
				<label class="label" for="el-deposit">{$t('leases.depositAmount')}</label>
				<input id="el-deposit" class="input" type="number" step="0.01" bind:value={editForm.deposit_amount} disabled={!canEdit} />
			</div>
			<div>
				<label class="label" for="el-late-type">{$t('leases.lateFeeType')}</label>
				<select id="el-late-type" class="input" bind:value={editForm.late_fee_type} disabled={!canEdit}>
					<option value="none">{$t('leases.none')}</option>
					<option value="fixed">{$t('leases.fixed')}</option>
					<option value="percentage">{$t('leases.percentage')}</option>
				</select>
			</div>
			{#if editForm.late_fee_type !== 'none'}
				<div class="grid grid-cols-2 gap-3">
					<div>
						<label class="label" for="el-late-val">{$t('leases.lateFeeValue')}</label>
						<input id="el-late-val" class="input" type="number" step="0.01" bind:value={editForm.late_fee_value} disabled={!canEdit} />
					</div>
					<div>
						<label class="label" for="el-grace">{$t('leases.gracePeriodDays')}</label>
						<input id="el-grace" class="input" type="number" bind:value={editForm.late_fee_grace_period_days} disabled={!canEdit} />
					</div>
				</div>
			{/if}
			<div>
				<label class="label" for="el-notes">{$t('common.notes')}</label>
				<textarea id="el-notes" class="input" rows="2" bind:value={editForm.notes} disabled={!canEdit} placeholder={$t('common.optional')}></textarea>
			</div>
		</div>

		<!-- Terminate confirm section -->
		{#if showTerminateConfirm && canEdit && editLease.status === 'active'}
			<div class="mt-5 border border-red-200 bg-red-50 p-4">
				<p class="mb-3 text-sm font-medium text-red-800">{$t('leases.terminateConfirm')}</p>
				<div class="mb-3">
					<label class="label" for="el-term-date">{$t('leases.endDate')}</label>
					<input id="el-term-date" class="input" type="date" bind:value={terminationDate} />
				</div>
				<div class="mb-3">
					<label class="label" for="el-term-reason">{$t('leases.terminateReason')}</label>
					<input
						id="el-term-reason"
						class="input"
						type="text"
						bind:value={terminationReason}
						placeholder={$t('common.required')}
					/>
				</div>
				<div class="flex gap-2">
					<button class="btn-secondary text-sm" on:click={() => (showTerminateConfirm = false)}>{$t('common.cancel')}</button>
					<button
						class="btn-danger text-sm"
						on:click={confirmTerminate}
						disabled={terminating || !terminationReason.trim()}
					>
						{terminating ? $t('common.saving') : $t('leases.terminate')}
					</button>
				</div>
			</div>
		{/if}

		<!-- Cascading delete: only reachable after a plain delete was refused -->
		{#if forcePlan && canForceDelete}
			<div class="mt-5 border-2 border-red-300 bg-red-50 p-4">
				<p class="mb-2 text-sm font-semibold text-red-900">
					⚠ {$t('leases.forceDeleteTitle')}
				</p>
				<p class="mb-1 text-xs text-red-800">{$t('leases.forceDeleteIntro')}</p>
				<ul class="mb-3 ml-4 list-disc text-xs text-red-800">
					{#each Object.entries(forcePlan.will_delete) as [key, n]}
						<li>{entityLabel(key, n)}</li>
					{/each}
				</ul>
				<p class="mb-3 text-xs text-red-700">{$t('leases.forceDeleteWarning')}</p>
				<div class="flex gap-2">
					<button class="btn-secondary text-sm" on:click={() => (forcePlan = null)}>
						{$t('common.cancel')}
					</button>
					<button class="btn-danger text-sm" on:click={confirmForceDelete} disabled={forceDeleting}>
						{forceDeleting ? $t('common.deleting') : $t('leases.deleteEverything')}
					</button>
				</div>
			</div>
		{/if}

	{/if}

	<!-- Record actions live in the body: an admin can have several of them and
	     they must never push the footer's Save/Close out of the panel. -->
	{#if editLease && (canEdit || canDelete)}
		<div class="danger-zone">
			<p class="danger-zone__title">{$t('common.recordActions')}</p>
			<p class="text-xs text-gray-600">{$t('common.deleteWarning')}</p>
			<div class="danger-zone__actions">
				{#if canEdit && editLease.status === 'draft'}
					<button class="btn-secondary btn-sm" on:click={activate}>{$t('leases.activate')}</button>
				{/if}
				{#if canEdit && editLease.status === 'active' && !showTerminateConfirm}
					<button class="btn-danger-quiet btn-sm" on:click={() => (showTerminateConfirm = true)}>
						{$t('leases.terminate')}
					</button>
				{/if}
				{#if canDelete && !showDeleteConfirm && !showTerminateConfirm && !forcePlan}
					<button class="btn-danger-quiet btn-sm" on:click={() => (showDeleteConfirm = true)}>
						{$t('common.delete')}
					</button>
				{/if}
				{#if showDeleteConfirm && canDelete}
					<span class="self-center text-xs font-medium text-red-800">
						{$t('common.confirmDelete')}
					</span>
					<button class="btn-secondary btn-sm" on:click={() => (showDeleteConfirm = false)}>
						{$t('common.cancel')}
					</button>
					<button class="btn-danger btn-sm" on:click={confirmDelete} disabled={deleting}>
						{deleting ? $t('common.deleting') : $t('common.delete')}
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<svelte:fragment slot="footer">
		<div class="action-bar">
			<button class="btn-secondary" on:click={() => (showDrawer = false)}>{$t('common.close')}</button>
			{#if canEdit && editLease?.status !== 'terminated' && editLease?.status !== 'expired'}
				<button class="btn-primary" on:click={saveEdit} disabled={editSaving}>
					{editSaving ? $t('common.saving') : $t('common.saveChanges')}
				</button>
			{/if}
		</div>
	</svelte:fragment>
</Drawer>

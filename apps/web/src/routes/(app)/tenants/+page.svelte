<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api } from '$lib/api/client';
	import type { Tenant } from '$lib/api/types';
	import { currentUser } from '$lib/stores/auth';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Drawer from '$lib/components/Drawer.svelte';

	let tenants: Tenant[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';
	let search = '';

	// Create modal
	let showModal = false;
	let form = {
		first_name: '',
		last_name: '',
		email: '',
		phone: '',
		is_company: false,
		company_name: ''
	};
	let saving = false;

	// Edit drawer
	let showDrawer = false;
	let editTenant: Tenant | null = null;
	let editForm = {
		first_name: '',
		last_name: '',
		company_name: '',
		is_company: false,
		email: '',
		phone: '',
		id_number: '',
		address: '',
		notes: ''
	};
	let editSaving = false;

	async function confirmDelete() {
		if (!editTenant) return;
		deleting = true;
		error = '';
		try {
			await api.tenants.delete(editTenant.id);
			showDrawer = false;
			showDeleteConfirm = false;
			await load();
		} catch (e) {
			// A 409 carries a message naming exactly what still references this record.
			error = e instanceof Error ? e.message : 'Error';
			showDeleteConfirm = false;
		} finally {
			deleting = false;
		}
	}

	$: canEdit = $currentUser?.role === 'admin' || $currentUser?.role === 'manager';
	// Mirrors the API: delete and lease-lifecycle actions are admin/manager only.
	$: canDelete = $currentUser?.role === 'admin' || $currentUser?.role === 'manager';

	let showDeleteConfirm = false;
	let deleting = false;

	async function load() {
		loading = true;
		try {
			const params = new URLSearchParams({ page: String(page), page_size: '25' });
			if (search) params.set('search', search);
			const res = await api.tenants.list(params.toString());
			tenants = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	onMount(load);

	async function save() {
		saving = true;
		try {
			await api.tenants.create(form);
			showModal = false;
			form = { first_name: '', last_name: '', email: '', phone: '', is_company: false, company_name: '' };
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			saving = false;
		}
	}

	function openDrawer(tenant: Tenant) {
		editTenant = tenant;
		editForm = {
			first_name: tenant.first_name,
			last_name: tenant.last_name,
			company_name: tenant.company_name,
			is_company: tenant.is_company,
			email: tenant.email,
			phone: tenant.phone,
			id_number: tenant.id_number ?? '',
			address: tenant.address ?? '',
			notes: tenant.notes ?? ''
		};
		showDeleteConfirm = false;
		showDrawer = true;
	}

	async function saveEdit() {
		if (!editTenant) return;
		editSaving = true;
		try {
			await api.tenants.update(editTenant.id, editForm);
			showDrawer = false;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			editSaving = false;
		}
	}
</script>

<svelte:head><title>{$t('tenants.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('tenants.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('tenants.subtitle')}</p>
			</div>
			{#if canEdit}
				<div class="flex-shrink-0">
					<button
						on:click={() => (showModal = true)}
						class="btn-on-dark"
					>+ {$t('tenants.addTenant')}</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<input
			type="text"
			class="input max-w-xs"
			placeholder={$t('tenants.searchPlaceholder')}
			bind:value={search}
			on:input={() => { page = 1; load(); }}
		/>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={tenants.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('tenants.displayName')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.email')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.phone')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.name')}</th>
			</tr>
		</svelte:fragment>
		{#each tenants as tn}
			<tr class="cursor-pointer hover:bg-gray-50" on:click={() => openDrawer(tn)}>
				<td class="px-4 py-3 font-medium text-gray-900">{tn.display_name}</td>
				<td class="px-4 py-3 text-gray-600">{tn.email}</td>
				<td class="px-4 py-3 text-gray-600">{tn.phone || '–'}</td>
				<td class="px-4 py-3 text-gray-600">{tn.is_company ? $t('common.company') : $t('common.individual')}</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- Create modal -->
<Modal bind:open={showModal} title={$t('tenants.newTenant')} on:close={() => (showModal = false)}>
	<form on:submit|preventDefault={save} class="space-y-4">
		<div class="flex items-center gap-2">
			<input id="is-company" type="checkbox" bind:checked={form.is_company} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="is-company" class="text-sm text-gray-700">{$t('tenants.isCompany')}</label>
		</div>
		{#if form.is_company}
			<div>
				<label class="label" for="company-name">{$t('tenants.companyName')}</label>
				<input id="company-name" class="input" bind:value={form.company_name} required />
			</div>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="label" for="t-fn">{$t('tenants.firstName')}</label>
					<input id="t-fn" class="input" bind:value={form.first_name} />
				</div>
				<div>
					<label class="label" for="t-ln">{$t('tenants.lastName')}</label>
					<input id="t-ln" class="input" bind:value={form.last_name} />
				</div>
			</div>
		{/if}
		<div>
			<label class="label" for="t-email">{$t('common.email')}</label>
			<input id="t-email" class="input" type="email" bind:value={form.email} required />
		</div>
		<div>
			<label class="label" for="t-phone">{$t('common.phone')}</label>
			<input id="t-phone" class="input" bind:value={form.phone} />
		</div>
	</form>
	<svelte:fragment slot="footer">
		<div class="flex justify-end gap-3">
			<button class="btn-secondary" on:click={() => (showModal = false)}>{$t('common.cancel')}</button>
			<button class="btn-primary" on:click={save} disabled={saving}>{saving ? $t('common.saving') : $t('common.save')}</button>
		</div>
	</svelte:fragment>
</Modal>

<!-- Edit / View drawer -->
<Drawer
	bind:open={showDrawer}
	title={canEdit ? $t('tenants.editTenant') : $t('tenants.title')}
	subtitle={editTenant?.display_name ?? ''}
	on:close={() => (showDrawer = false)}
>
	{#if !canEdit}
		<p class="mb-4 bg-amber-50 px-3 py-2 text-xs text-amber-700">
			{$t('tenants.readOnlyNotice')}
		</p>
	{/if}
	<div class="space-y-4">
		<div class="flex items-center gap-2">
			<input id="et-is-company" type="checkbox" bind:checked={editForm.is_company} disabled={!canEdit} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="et-is-company" class="text-sm text-gray-700">{$t('tenants.isCompany')}</label>
		</div>
		{#if editForm.is_company}
			<div>
				<label class="label" for="et-company">{$t('tenants.companyName')}</label>
				<input id="et-company" class="input" bind:value={editForm.company_name} disabled={!canEdit} />
			</div>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="label" for="et-fn">{$t('tenants.firstName')}</label>
					<input id="et-fn" class="input" bind:value={editForm.first_name} disabled={!canEdit} />
				</div>
				<div>
					<label class="label" for="et-ln">{$t('tenants.lastName')}</label>
					<input id="et-ln" class="input" bind:value={editForm.last_name} disabled={!canEdit} />
				</div>
			</div>
		{/if}
		<div>
			<label class="label" for="et-email">{$t('common.email')}</label>
			<input id="et-email" class="input" type="email" bind:value={editForm.email} disabled={!canEdit} />
		</div>
		<div>
			<label class="label" for="et-phone">{$t('common.phone')}</label>
			<input id="et-phone" class="input" bind:value={editForm.phone} disabled={!canEdit} />
		</div>
		<div>
			<label class="label" for="et-id">{$t('tenants.idNumber')}</label>
			<input id="et-id" class="input" bind:value={editForm.id_number} disabled={!canEdit} placeholder={$t('common.optional')} />
		</div>
		<div>
			<label class="label" for="et-address">{$t('common.address')}</label>
			<textarea id="et-address" class="input" rows="2" bind:value={editForm.address} disabled={!canEdit} placeholder={$t('common.optional')}></textarea>
		</div>
		<div>
			<label class="label" for="et-notes">{$t('common.notes')}</label>
			<textarea id="et-notes" class="input" rows="2" bind:value={editForm.notes} disabled={!canEdit} placeholder={$t('common.optional')}></textarea>
		</div>
	</div>
	<!-- Record actions live in the body, so the footer can never overflow -->
	{#if canDelete && editTenant}
		<div class="danger-zone">
			<p class="danger-zone__title">{$t('common.dangerZone')}</p>
			<p class="text-xs text-gray-600">{$t('common.deleteWarning')}</p>
			<div class="danger-zone__actions">
				{#if showDeleteConfirm}
					<span class="self-center text-xs font-medium text-red-800">
						{$t('common.confirmDelete')}
					</span>
					<button class="btn-secondary btn-sm" on:click={() => (showDeleteConfirm = false)}>
						{$t('common.cancel')}
					</button>
					<button class="btn-danger btn-sm" on:click={confirmDelete} disabled={deleting}>
						{deleting ? $t('common.deleting') : $t('common.delete')}
					</button>
				{:else}
					<button class="btn-danger-quiet btn-sm" on:click={() => (showDeleteConfirm = true)}>
						{$t('common.delete')}
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<svelte:fragment slot="footer">
		<div class="action-bar">
			<button class="btn-secondary" on:click={() => (showDrawer = false)}>{$t('common.close')}</button>
			{#if canEdit}
				<button class="btn-primary" on:click={saveEdit} disabled={editSaving}>
					{editSaving ? $t('common.saving') : $t('common.saveChanges')}
				</button>
			{/if}
		</div>
	</svelte:fragment>
</Drawer>

<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import type { Owner } from '$lib/api/types';
	import { currentUser } from '$lib/stores/auth';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Drawer from '$lib/components/Drawer.svelte';
	import { t } from 'svelte-i18n';

	let owners: Owner[] = [];
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
		company_name: '',
		is_company: false,
		email: '',
		phone: '',
		address: '',
		notes: ''
	};
	let saving = false;

	// Edit drawer
	let showDrawer = false;
	let editOwner: Owner | null = null;
	let editForm = {
		first_name: '',
		last_name: '',
		company_name: '',
		is_company: false,
		email: '',
		phone: '',
		address: '',
		notes: ''
	};
	let editSaving = false;

	async function confirmDelete() {
		if (!editOwner) return;
		deleting = true;
		error = '';
		try {
			await api.owners.delete(editOwner.id);
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
			const res = await api.owners.list(params.toString());
			owners = res.results;
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
			await api.owners.create(form);
			showModal = false;
			form = { first_name: '', last_name: '', company_name: '', is_company: false, email: '', phone: '', address: '', notes: '' };
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('common.somethingWentWrong');
		} finally {
			saving = false;
		}
	}

	function openDrawer(owner: Owner) {
		editOwner = owner;
		editForm = {
			first_name: owner.first_name,
			last_name: owner.last_name,
			company_name: owner.company_name,
			is_company: owner.is_company,
			email: owner.email,
			phone: owner.phone,
			address: owner.address ?? '',
			notes: owner.notes ?? ''
		};
		showDeleteConfirm = false;
		showDrawer = true;
	}

	async function saveEdit() {
		if (!editOwner) return;
		editSaving = true;
		try {
			await api.owners.update(editOwner.id, editForm);
			showDrawer = false;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('common.somethingWentWrong');
		} finally {
			editSaving = false;
		}
	}

	function onSearch() {
		page = 1;
		load();
	}
</script>

<svelte:head><title>{$t('owners.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('owners.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('owners.subtitle')}</p>
			</div>
			{#if canEdit}
				<div class="flex-shrink-0">
					<button
						on:click={() => (showModal = true)}
						class="btn-on-dark"
					>+ {$t('owners.addOwner')}</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<input
			type="text"
			class="input max-w-xs"
			placeholder={$t('owners.searchPlaceholder')}
			bind:value={search}
			on:input={onSearch}
		/>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={owners.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('owners.displayName')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.email')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.phone')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.propertyType')}</th>
			</tr>
		</svelte:fragment>
		{#each owners as o}
			<tr class="cursor-pointer hover:bg-gray-50" on:click={() => openDrawer(o)}>
				<td class="px-4 py-3 font-medium text-gray-900">{o.display_name}</td>
				<td class="px-4 py-3 text-gray-600">{o.email || '–'}</td>
				<td class="px-4 py-3 text-gray-600">{o.phone || '–'}</td>
				<td class="px-4 py-3 text-gray-600">{o.is_company ? 'Company' : 'Individual'}</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- Create modal -->
<Modal bind:open={showModal} title={$t('owners.addOwner')} on:close={() => (showModal = false)}>
	<form on:submit|preventDefault={save} class="space-y-4">
		<div class="flex items-center gap-2">
			<input id="is-company" type="checkbox" bind:checked={form.is_company} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="is-company" class="text-sm text-gray-700">{$t('owners.isCompany')}</label>
		</div>
		{#if form.is_company}
			<div>
				<label class="label" for="o-company">{$t('owners.companyName')}</label>
				<input id="o-company" class="input" bind:value={form.company_name} required />
			</div>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="label" for="o-fn">{$t('owners.firstName')}</label>
					<input id="o-fn" class="input" bind:value={form.first_name} />
				</div>
				<div>
					<label class="label" for="o-ln">{$t('owners.lastName')}</label>
					<input id="o-ln" class="input" bind:value={form.last_name} />
				</div>
			</div>
		{/if}
		<div>
			<label class="label" for="o-email">{$t('common.email')}</label>
			<input id="o-email" class="input" type="email" bind:value={form.email} required />
		</div>
		<div>
			<label class="label" for="o-phone">{$t('common.phone')}</label>
			<input id="o-phone" class="input" bind:value={form.phone} />
		</div>
		<div>
			<label class="label" for="o-address">{$t('properties.addressLine1')}</label>
			<textarea id="o-address" class="input" rows="2" bind:value={form.address}></textarea>
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
	title={canEdit ? $t('owners.editOwner') : $t('owners.title')}
	subtitle={editOwner?.display_name ?? ''}
	on:close={() => (showDrawer = false)}
>
	{#if !canEdit}
		<p class="mb-4 bg-amber-50 px-3 py-2 text-xs text-amber-700">
			{$t('owners.readOnlyNotice')}
		</p>
	{/if}
	<div class="space-y-4">
		<div class="flex items-center gap-2">
			<input
				id="e-is-company"
				type="checkbox"
				bind:checked={editForm.is_company}
				disabled={!canEdit}
				class="h-4 w-4 border-gray-300 text-primary-600"
			/>
			<label for="e-is-company" class="text-sm text-gray-700">{$t('owners.isCompany')}</label>
		</div>
		{#if editForm.is_company}
			<div>
				<label class="label" for="e-company">{$t('owners.companyName')}</label>
				<input id="e-company" class="input" bind:value={editForm.company_name} disabled={!canEdit} />
			</div>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="label" for="e-fn">{$t('owners.firstName')}</label>
					<input id="e-fn" class="input" bind:value={editForm.first_name} disabled={!canEdit} />
				</div>
				<div>
					<label class="label" for="e-ln">{$t('owners.lastName')}</label>
					<input id="e-ln" class="input" bind:value={editForm.last_name} disabled={!canEdit} />
				</div>
			</div>
		{/if}
		<div>
			<label class="label" for="e-email">{$t('common.email')}</label>
			<input id="e-email" class="input" type="email" bind:value={editForm.email} disabled={!canEdit} />
		</div>
		<div>
			<label class="label" for="e-phone">{$t('common.phone')}</label>
			<input id="e-phone" class="input" bind:value={editForm.phone} disabled={!canEdit} />
		</div>
		<div>
			<label class="label" for="e-address">{$t('properties.addressLine1')}</label>
			<textarea id="e-address" class="input" rows="2" bind:value={editForm.address} disabled={!canEdit}></textarea>
		</div>
		<div>
			<label class="label" for="e-notes">Notes</label>
			<textarea id="e-notes" class="input" rows="2" bind:value={editForm.notes} disabled={!canEdit}></textarea>
		</div>
	</div>
	<!-- Record actions live in the body, so the footer can never overflow -->
	{#if canDelete && editOwner}
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

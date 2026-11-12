<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import type { Property, Owner } from '$lib/api/types';
	import { currentUser } from '$lib/stores/auth';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Drawer from '$lib/components/Drawer.svelte';
	import { t } from 'svelte-i18n';

	let properties: Property[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';
	let search = '';
	let owners: Owner[] = [];

	// Create modal
	let showModal = false;
	let form = {
		name: '',
		property_type: 'residential',
		owner: '',
		address_line1: '',
		city: 'Ndjamena',
		country: 'Tchad'
	};
	let saving = false;

	// Edit drawer
	let showDrawer = false;
	let editProperty: Property | null = null;
	let editForm = {
		name: '',
		property_type: 'residential',
		owner: '' as string | number,
		address_line1: '',
		address_line2: '',
		city: '',
		country: '',
		postal_code: '',
		description: ''
	};
	let editSaving = false;

	async function confirmDelete() {
		if (!editProperty) return;
		deleting = true;
		error = '';
		try {
			await api.properties.delete(editProperty.id);
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
			const res = await api.properties.list(params.toString());
			properties = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
		} finally {
			loading = false;
		}
	}

	async function loadOwners() {
		try {
			const res = await api.owners.list('page_size=1000');
			owners = res.results;
		} catch {}
	}

	onMount(() => { load(); loadOwners(); });

	async function save() {
		saving = true;
		try {
			await api.properties.create(form);
			showModal = false;
			form = { name: '', property_type: 'residential', owner: '', address_line1: '', city: 'Ndjamena', country: 'Tchad' };
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('common.somethingWentWrong');
		} finally {
			saving = false;
		}
	}

	function openDrawer(property: Property) {
		editProperty = property;
		editForm = {
			name: property.name,
			property_type: property.property_type,
			owner: property.owner,
			address_line1: property.address_line1,
			address_line2: property.address_line2 ?? '',
			city: property.city,
			country: property.country,
			postal_code: property.postal_code ?? '',
			description: property.description ?? ''
		};
		showDeleteConfirm = false;
		showDrawer = true;
	}

	async function saveEdit() {
		if (!editProperty) return;
		editSaving = true;
		try {
			await api.properties.update(editProperty.id, {
				...editForm,
				owner: Number(editForm.owner)
			});
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

<svelte:head><title>{$t('properties.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('properties.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('properties.subtitle')}</p>
			</div>
			{#if canEdit}
				<div class="flex-shrink-0">
					<button
						on:click={() => (showModal = true)}
						class="btn-on-dark"
					>+ {$t('properties.addProperty')}</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<input
			type="text"
			class="input max-w-xs"
			placeholder={$t('properties.searchPlaceholder')}
			bind:value={search}
			on:input={onSearch}
		/>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={properties.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('common.name')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.propertyType')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.owner')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.city')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.units')}</th>
			</tr>
		</svelte:fragment>
		{#each properties as p}
			<tr class="cursor-pointer hover:bg-gray-50" on:click={() => openDrawer(p)}>
				<td class="px-4 py-3 font-medium text-gray-900">{p.name}</td>
				<td class="px-4 py-3 capitalize text-gray-600">{p.property_type}</td>
				<td class="px-4 py-3 text-gray-600">{p.owner_name}</td>
				<td class="px-4 py-3 text-gray-600">{p.city}</td>
				<td class="px-4 py-3 text-gray-600">{p.unit_count}</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- Create modal -->
<Modal bind:open={showModal} title={$t('properties.newProperty')} on:close={() => (showModal = false)}>
	<form on:submit|preventDefault={save} class="space-y-4">
		<div>
			<label class="label" for="p-name">{$t('common.name')}</label>
			<input id="p-name" class="input" bind:value={form.name} required />
		</div>
		<div>
			<label class="label" for="p-type">{$t('properties.propertyType')}</label>
			<select id="p-type" class="input" bind:value={form.property_type}>
				<option value="residential">{$t('properties.residential')}</option>
				<option value="commercial">{$t('properties.commercial')}</option>
				<option value="mixed">{$t('properties.mixed')}</option>
				<option value="industrial">Industrial</option>
			</select>
		</div>
		<div>
			<label class="label" for="p-owner">{$t('properties.owner')}</label>
			<select id="p-owner" class="input" bind:value={form.owner} required>
				<option value="" disabled>{$t('properties.selectOwner')}</option>
				{#each owners as o}
					<option value={o.id}>{o.display_name}</option>
				{/each}
			</select>
		</div>
		<div>
			<label class="label" for="p-addr">{$t('properties.addressLine1')}</label>
			<input id="p-addr" class="input" bind:value={form.address_line1} required />
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="p-city">{$t('properties.city')}</label>
				<input id="p-city" class="input" bind:value={form.city} required />
			</div>
			<div>
				<label class="label" for="p-country">{$t('properties.country')}</label>
				<input id="p-country" class="input" bind:value={form.country} required />
			</div>
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
	title={canEdit ? $t('properties.editProperty') : $t('nav.properties')}
	subtitle={editProperty?.name ?? ''}
	on:close={() => (showDrawer = false)}
>
	{#if !canEdit}
		<p class="mb-4 bg-amber-50 px-3 py-2 text-xs text-amber-700">
			{$t('properties.readOnlyNotice')}
		</p>
	{/if}
	<div class="space-y-4">
		<div>
			<label class="label" for="ep-name">{$t('common.name')}</label>
			<input id="ep-name" class="input" bind:value={editForm.name} disabled={!canEdit} required />
		</div>
		<div>
			<label class="label" for="ep-type">{$t('properties.propertyType')}</label>
			<select id="ep-type" class="input" bind:value={editForm.property_type} disabled={!canEdit}>
				<option value="residential">{$t('properties.residential')}</option>
				<option value="commercial">{$t('properties.commercial')}</option>
				<option value="mixed">{$t('properties.mixed')}</option>
				<option value="industrial">Industrial</option>
			</select>
		</div>
		<div>
			<label class="label" for="ep-owner">{$t('properties.owner')}</label>
			<select id="ep-owner" class="input" bind:value={editForm.owner} disabled={!canEdit}>
				{#each owners as o}
					<option value={o.id}>{o.display_name}</option>
				{/each}
			</select>
		</div>
		<div>
			<label class="label" for="ep-addr1">{$t('properties.addressLine1')}</label>
			<input id="ep-addr1" class="input" bind:value={editForm.address_line1} disabled={!canEdit} />
		</div>
		<div>
			<label class="label" for="ep-addr2">{$t('properties.addressLine2')}</label>
			<input id="ep-addr2" class="input" bind:value={editForm.address_line2} disabled={!canEdit} placeholder={$t('common.optional')} />
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="ep-city">{$t('properties.city')}</label>
				<input id="ep-city" class="input" bind:value={editForm.city} disabled={!canEdit} />
			</div>
			<div>
				<label class="label" for="ep-country">{$t('properties.country')}</label>
				<input id="ep-country" class="input" bind:value={editForm.country} disabled={!canEdit} />
			</div>
		</div>
		<div>
			<label class="label" for="ep-desc">{$t('units.description')}</label>
			<textarea id="ep-desc" class="input" rows="2" bind:value={editForm.description} disabled={!canEdit} placeholder={$t('common.optional')}></textarea>
		</div>
	</div>
	<!-- Record actions live in the body, so the footer can never overflow -->
	{#if canDelete && editProperty}
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

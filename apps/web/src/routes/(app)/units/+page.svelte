<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import type { Unit, Property } from '$lib/api/types';
	import { currentUser } from '$lib/stores/auth';
	import DataTable from '$lib/components/DataTable.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Drawer from '$lib/components/Drawer.svelte';
	import { t } from 'svelte-i18n';

	let units: Unit[] = [];
	let count = 0;
	let page = 1;
	let loading = true;
	let error = '';
	let search = '';
	let propertyOptions: Property[] = [];

	// Create modal
	let showModal = false;
	let saving = false;
	let form = {
		building: '',
		name: '',
		unit_type: 'apartment',
		floor: '',
		surface_area: '',
		is_active: true
	};

	// Edit drawer
	let showDrawer = false;
	let editUnit: Unit | null = null;
	let editForm = {
		building: '' as string | number,
		name: '',
		unit_type: 'apartment',
		floor: '' as string | number,
		surface_area: '' as string | number,
		description: '',
		is_active: true
	};
	let editSaving = false;

	async function confirmDelete() {
		if (!editUnit) return;
		deleting = true;
		error = '';
		try {
			await api.units.delete(editUnit.id);
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
			const res = await api.units.list(params.toString());
			units = res.results;
			count = res.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Error';
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

	onMount(() => { load(); loadProperties(); });

	async function save() {
		saving = true;
		try {
			await api.units.create({
				...form,
				building: Number(form.building),
				floor: form.floor ? Number(form.floor) : null,
				surface_area: form.surface_area ? Number(form.surface_area) : null
			});
			showModal = false;
			form = { building: '', name: '', unit_type: 'apartment', floor: '', surface_area: '', is_active: true };
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('common.somethingWentWrong');
		} finally {
			saving = false;
		}
	}

	function openDrawer(unit: Unit) {
		editUnit = unit;
		editForm = {
			building: unit.building,
			name: unit.name,
			unit_type: unit.unit_type,
			floor: unit.floor ?? '',
			surface_area: unit.surface_area ?? '',
			description: unit.description ?? '',
			is_active: unit.is_active
		};
		showDeleteConfirm = false;
		showDrawer = true;
	}

	async function saveEdit() {
		if (!editUnit) return;
		editSaving = true;
		try {
			await api.units.update(editUnit.id, {
				...editForm,
				building: Number(editForm.building),
				floor: editForm.floor !== '' ? Number(editForm.floor) : null,
				surface_area: editForm.surface_area !== '' ? Number(editForm.surface_area) : null
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

<svelte:head><title>{$t('units.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<!-- Hero -->
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('units.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('units.subtitle')}</p>
			</div>
			{#if canEdit}
				<div class="flex-shrink-0">
					<button
						on:click={() => (showModal = true)}
						class="btn-on-dark"
					>+ {$t('units.addUnit')}</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<input
			type="text"
			class="input max-w-xs"
			placeholder={$t('units.searchPlaceholder')}
			bind:value={search}
			on:input={onSearch}
		/>
	</div>

	{#if error}<div class="text-sm text-red-600">{error}</div>{/if}

	<DataTable {loading} empty={units.length === 0}>
		<svelte:fragment slot="head">
			<tr>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('units.property')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('units.unitName')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('properties.propertyType')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('units.floor')}</th>
				<th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">{$t('units.status')}</th>
			</tr>
		</svelte:fragment>
		{#each units as u}
			<tr class="cursor-pointer hover:bg-gray-50" on:click={() => openDrawer(u)}>
				<td class="px-4 py-3 text-gray-600">{u.property_name}</td>
				<td class="px-4 py-3 font-medium text-gray-900">{u.name}</td>
				<td class="px-4 py-3 capitalize text-gray-600">{u.unit_type}</td>
				<td class="px-4 py-3 text-gray-600">{u.floor ?? '–'}</td>
				<td class="px-4 py-3">
					{#if u.is_occupied}
						<span class="badge bg-green-100 text-green-700">{$t('units.occupied')}</span>
					{:else}
						<span class="badge bg-gray-100 text-gray-500">{$t('units.vacant')}</span>
					{/if}
				</td>
			</tr>
		{/each}
	</DataTable>

	<Pagination {count} {page} on:change={(e) => { page = e.detail; load(); }} />
</div>

<!-- Create modal -->
<Modal bind:open={showModal} title={$t('units.addUnit')} on:close={() => (showModal = false)}>
	<form on:submit|preventDefault={save} class="space-y-4">
		<div>
			<label class="label" for="u-building">{$t('units.property')}</label>
			<select id="u-building" class="input" bind:value={form.building} required>
				<option value="" disabled>{$t('units.selectProperty')}</option>
				{#each propertyOptions as p}
					<option value={p.id}>{p.name}</option>
				{/each}
			</select>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="u-name">{$t('units.unitName')}</label>
				<input id="u-name" class="input" bind:value={form.name} required />
			</div>
			<div>
				<label class="label" for="u-type">{$t('properties.propertyType')}</label>
				<select id="u-type" class="input" bind:value={form.unit_type}>
					<option value="apartment">{$t('units.apartment')}</option>
					<option value="studio">{$t('units.studio')}</option>
					<option value="villa">Villa</option>
					<option value="office">{$t('units.office')}</option>
					<option value="shop">{$t('units.shop')}</option>
					<option value="warehouse">{$t('units.warehouse')}</option>
					<option value="parking">Parking</option>
					<option value="other">{$t('units.other')}</option>
				</select>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="u-floor">{$t('units.floor')}</label>
				<input id="u-floor" class="input" type="number" bind:value={form.floor} placeholder={$t('common.optional')} />
			</div>
			<div>
				<label class="label" for="u-area">{$t('units.area')}</label>
				<input id="u-area" class="input" type="number" step="0.01" bind:value={form.surface_area} placeholder={$t('common.optional')} />
			</div>
		</div>
		<div class="flex items-center gap-2">
			<input id="u-active" type="checkbox" bind:checked={form.is_active} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="u-active" class="text-sm text-gray-700">Active</label>
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
	title={canEdit ? $t('units.editUnit') : $t('units.title')}
	subtitle={editUnit ? `${editUnit.name} · ${editUnit.property_name}` : ''}
	on:close={() => (showDrawer = false)}
>
	{#if !canEdit}
		<p class="mb-4 bg-amber-50 px-3 py-2 text-xs text-amber-700">
			{$t('units.readOnlyNotice')}
		</p>
	{/if}
	<div class="space-y-4">
		<div>
			<label class="label" for="eu-building">{$t('units.property')}</label>
			<select id="eu-building" class="input" bind:value={editForm.building} disabled={!canEdit}>
				{#each propertyOptions as p}
					<option value={p.id}>{p.name}</option>
				{/each}
			</select>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="eu-name">{$t('units.unitName')}</label>
				<input id="eu-name" class="input" bind:value={editForm.name} disabled={!canEdit} />
			</div>
			<div>
				<label class="label" for="eu-type">{$t('properties.propertyType')}</label>
				<select id="eu-type" class="input" bind:value={editForm.unit_type} disabled={!canEdit}>
					<option value="apartment">{$t('units.apartment')}</option>
					<option value="studio">{$t('units.studio')}</option>
					<option value="villa">Villa</option>
					<option value="office">{$t('units.office')}</option>
					<option value="shop">{$t('units.shop')}</option>
					<option value="warehouse">{$t('units.warehouse')}</option>
					<option value="parking">Parking</option>
					<option value="other">{$t('units.other')}</option>
				</select>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-3">
			<div>
				<label class="label" for="eu-floor">{$t('units.floor')}</label>
				<input id="eu-floor" class="input" type="number" bind:value={editForm.floor} disabled={!canEdit} placeholder={$t('common.optional')} />
			</div>
			<div>
				<label class="label" for="eu-area">{$t('units.area')}</label>
				<input id="eu-area" class="input" type="number" step="0.01" bind:value={editForm.surface_area} disabled={!canEdit} placeholder={$t('common.optional')} />
			</div>
		</div>
		<div>
			<label class="label" for="eu-desc">{$t('units.description')}</label>
			<textarea id="eu-desc" class="input" rows="2" bind:value={editForm.description} disabled={!canEdit} placeholder={$t('common.optional')}></textarea>
		</div>
		<div class="flex items-center gap-2">
			<input id="eu-active" type="checkbox" bind:checked={editForm.is_active} disabled={!canEdit} class="h-4 w-4 border-gray-300 text-primary-600" />
			<label for="eu-active" class="text-sm text-gray-700">Active</label>
		</div>
	</div>
	<!-- Record actions live in the body, so the footer can never overflow -->
	{#if canDelete && editUnit}
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

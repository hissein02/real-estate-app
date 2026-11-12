<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { t } from 'svelte-i18n';

	export let count = 0;
	export let pageSize = 25;
	export let page = 1;

	const dispatch = createEventDispatcher<{ change: number }>();

	$: totalPages = Math.ceil(count / pageSize);
	$: start = (page - 1) * pageSize + 1;
	$: end = Math.min(page * pageSize, count);
</script>

{#if count > 0}
	<div class="flex items-center justify-between px-1 py-3 text-sm text-gray-600">
		<span>{$t('pagination.showing')} {start}–{end} {$t('pagination.of')} {count} {$t('pagination.results')}</span>
		<div class="flex gap-1">
			<button
				class="btn-secondary px-3 py-1.5 text-xs"
				disabled={page <= 1}
				on:click={() => dispatch('change', page - 1)}
			>
				{$t('pagination.previous')}
			</button>
			<span class="flex items-center px-3 text-xs">{$t('pagination.page')} {page} {$t('pagination.of')} {totalPages}</span>
			<button
				class="btn-secondary px-3 py-1.5 text-xs"
				disabled={page >= totalPages}
				on:click={() => dispatch('change', page + 1)}
			>
				{$t('pagination.next')}
			</button>
		</div>
	</div>
{/if}

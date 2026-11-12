<script lang="ts">
	import { t } from 'svelte-i18n';

	export let loading = false;
	export let empty = false;
	export let emptyMessage = '';
</script>

<div class="overflow-x-auto border border-gray-200">
	<table class="min-w-full divide-y divide-gray-200 bg-white text-sm">
		<thead class="bg-gray-50">
			<slot name="head" />
		</thead>
		<tbody class="divide-y divide-gray-100">
			{#if loading}
				<tr>
					<td colspan="99" class="py-12 text-center">
						<div class="flex flex-col items-center gap-2 text-gray-500">
							<svg class="h-6 w-6 animate-spin text-primary-600" fill="none" viewBox="0 0 24 24">
								<circle
									class="opacity-25"
									cx="12"
									cy="12"
									r="10"
									stroke="currentColor"
									stroke-width="4"
								/>
								<path
									class="opacity-75"
									fill="currentColor"
									d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
								/>
							</svg>
							<span class="text-sm">{$t('dataTable.loading')}</span>
						</div>
					</td>
				</tr>
			{:else if empty}
				<tr>
					<td colspan="99" class="py-12 text-center text-gray-500">
						<p class="font-medium">{emptyMessage || $t('dataTable.noData')}</p>
						<p class="mt-1 text-xs text-gray-400">{$t('table.noDataDescription')}</p>
					</td>
				</tr>
			{:else}
				<slot />
			{/if}
		</tbody>
	</table>
</div>

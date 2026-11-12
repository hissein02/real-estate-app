<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { t } from 'svelte-i18n';

	export let open = false;
	export let title = '';
	export let subtitle = '';

	const dispatch = createEventDispatcher();

	function close() {
		dispatch('close');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<div class="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
		<!-- Backdrop -->
		<div
			class="absolute inset-0 bg-slate-900/30"
			on:click={close}
			role="presentation"
		></div>

		<!-- Panel -->
		<div class="relative flex h-full w-full max-w-xl flex-col border-l border-gray-200 bg-white animate-slide-in">
			<!-- Header -->
			<div class="flex-shrink-0 border-b border-gray-200 px-6 py-4">
				<div class="flex items-center justify-between">
					<div class="min-w-0 flex-1">
						<h2 class="truncate text-lg font-semibold text-gray-900">{title}</h2>
						{#if subtitle}
							<p class="truncate text-sm text-gray-500">{subtitle}</p>
						{/if}
					</div>
					<button
						on:click={close}
						title={$t('drawer.close')}
						aria-label={$t('drawer.close')}
						class="ml-4 flex-shrink-0 p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
					>
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Body -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				<slot />
			</div>

			<!-- Footer -->
			{#if $$slots.footer}
				<div class="flex-shrink-0 border-t border-gray-200 px-6 py-4">
					<slot name="footer" />
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	@keyframes slideIn {
		from { transform: translateX(100%); }
		to { transform: translateX(0); }
	}
	.animate-slide-in {
		animation: slideIn 0.25s ease-out;
	}
</style>

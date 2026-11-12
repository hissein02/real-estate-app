<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { t } from 'svelte-i18n';

	export let open = false;
	export let title = '';
	export let maxWidth: 'sm' | 'md' | 'lg' | 'xl' | '4xl' = 'md';

	const dispatch = createEventDispatcher();
	// '4xl' is wide enough for an A4 document (794px) plus the modal padding.
	const widths = {
		sm: 'max-w-sm',
		md: 'max-w-md',
		lg: 'max-w-lg',
		xl: 'max-w-xl',
		'4xl': 'max-w-4xl'
	};

	function close() {
		dispatch('close');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
		on:click|self={close}
		role="dialog"
		aria-modal="true"
		aria-label={title}
	>
		<div class="card w-full {widths[maxWidth]}">
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
				<h2 class="text-lg font-semibold text-gray-900">{title}</h2>
				<button
					type="button"
					class="p-1.5 text-gray-500 hover:bg-gray-100"
					on:click={close}
					aria-label={$t('modal.close')}
				>
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			</div>
			<!-- Body -->
			<div class="px-6 py-4">
				<slot />
			</div>
			<!-- Footer -->
			{#if $$slots.footer}
				<div class="border-t border-gray-200 px-6 py-4">
					<slot name="footer" />
				</div>
			{/if}
		</div>
	</div>
{/if}

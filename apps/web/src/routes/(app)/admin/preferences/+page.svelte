<script lang="ts">
	import { t } from 'svelte-i18n';
	import { setLocale, getSavedLocale, type SupportedLocale } from '$lib/i18n';
	import { onMount } from 'svelte';

	let selectedLocale: SupportedLocale = 'en';
	let saved = false;
	let saveTimeout: ReturnType<typeof setTimeout>;

	onMount(() => {
		selectedLocale = getSavedLocale();
	});

	function handleSave() {
		setLocale(selectedLocale);
		saved = true;
		clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => (saved = false), 3000);
	}

	// The language's own name identifies it; a flag identifies a country, not a language.
	const languages: { code: SupportedLocale; label: string; nativeLabel: string }[] = [
		{ code: 'en', label: 'English', nativeLabel: 'English' },
		{ code: 'fr', label: 'French', nativeLabel: 'Français' }
	];
</script>

<svelte:head><title>{$t('preferences.title')} – RealEstate</title></svelte:head>

<div class="space-y-4">
	<div class="px-6 py-5" style="background: #031927">
		<div class="flex items-center gap-4">
			<a
				href="/admin"
				aria-label={$t('common.back')}
				class="inline-flex items-center justify-center p-1.5 transition-colors hover:bg-white/10"
				style="color: #9dd1f1"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
			</a>
			<div>
				<h1 class="text-2xl font-bold text-white">{$t('preferences.title')}</h1>
				<p class="mt-1 text-sm" style="color: #9dd1f1">{$t('preferences.subtitle')}</p>
			</div>
		</div>
	</div>

	<div class="card">
		<div class="border-b border-gray-200 px-5 py-4">
			<h2 class="text-sm font-semibold text-gray-900">{$t('preferences.sectionLanguage')}</h2>
			<p class="mt-0.5 text-xs text-gray-500">{$t('preferences.languageDescription')}</p>
		</div>

		<div class="p-5">
			<fieldset>
				<legend class="sr-only">{$t('preferences.sectionLanguage')}</legend>
				{#each languages as lang}
					<label class="flex cursor-pointer items-center gap-3 py-2">
						<input
							type="radio"
							name="locale"
							value={lang.code}
							bind:group={selectedLocale}
							class="h-4 w-4 accent-primary-600"
						/>
						<span class="text-sm text-gray-900">{lang.nativeLabel}</span>
						{#if lang.nativeLabel !== lang.label}
							<span class="text-xs text-gray-500">{lang.label}</span>
						{/if}
					</label>
				{/each}
			</fieldset>
		</div>

		<div class="flex items-center justify-end gap-3 border-t border-gray-200 px-5 py-4">
			{#if saved}
				<!-- Quiet inline confirmation rather than a coloured banner. -->
				<span class="text-xs text-gray-500" role="status">{$t('preferences.saved')}</span>
			{/if}
			<button class="btn-primary" on:click={handleSave}>{$t('common.saveChanges')}</button>
		</div>
	</div>
</div>

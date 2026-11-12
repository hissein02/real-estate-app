<script lang="ts">
	// Root layout – minimal, just apply global styles
	import '../app.css';
	import { waitLocale } from '$lib/i18n';
</script>

{#await waitLocale()}
	<!-- locale loading – no flash, nearly instant -->
{:then}
	<slot />
{/await}

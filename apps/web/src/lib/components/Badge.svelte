<script lang="ts">
	import type { BadgeVariant } from '$lib/utils/status';
	import { VARIANT_CLASSES } from '$lib/utils/status';

	export let variant: BadgeVariant = 'gray';
	export let label: string = '';
</script>

<span class="badge {VARIANT_CLASSES[variant]}">{label}</span>

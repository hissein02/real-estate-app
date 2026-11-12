<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import { mediaUrl } from '$lib/api/client';

	export let currentLogoUrl: string | null = null;
	export let uploading = false;

	const dispatch = createEventDispatcher<{
		upload: File;
		remove: void;
	}>();

	const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'];
	const ACCEPTED_EXTENSIONS = '.png,.jpg,.jpeg,.webp,.svg';
	const MAX_SIZE_MB = 2;
	const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

	let selectedFile: File | null = null;
	let previewUrl: string | null = null;
	let isSvg = false;
	let originalWidth = 0;
	let originalHeight = 0;
	let resizeScale = 100;
	let resizedBlob: Blob | null = null;
	let fileInput: HTMLInputElement;
	let dragOver = false;
	let error: string | null = null;
	let imageLoaded = false;

	onDestroy(() => {
		if (previewUrl) URL.revokeObjectURL(previewUrl);
	});

	function validateFile(file: File): string | null {
		if (file.size > MAX_SIZE_BYTES) {
			return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is ${MAX_SIZE_MB} MB.`;
		}
		if (!ACCEPTED_TYPES.includes(file.type) && !file.name.match(/\.(png|jpe?g|webp|svg)$/i)) {
			return 'Unsupported file type. Allowed: PNG, JPG, WEBP, SVG.';
		}
		return null;
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		if (input.files?.[0]) {
			processFile(input.files[0]);
		}
	}

	function handleDrop(event: DragEvent) {
		dragOver = false;
		const file = event.dataTransfer?.files?.[0];
		if (file) processFile(file);
	}

	function processFile(file: File) {
		error = null;
		const validationError = validateFile(file);
		if (validationError) {
			error = validationError;
			return;
		}

		selectedFile = file;
		isSvg = file.type === 'image/svg+xml' || file.name.toLowerCase().endsWith('.svg');
		resizeScale = 100;
		resizedBlob = null;
		imageLoaded = false;

		if (previewUrl) URL.revokeObjectURL(previewUrl);

		if (isSvg) {
			previewUrl = URL.createObjectURL(file);
		} else {
			loadAndPreview(file);
		}
	}

	function loadAndPreview(file: File) {
		const img = new Image();
		const url = URL.createObjectURL(file);
		img.onload = () => {
			originalWidth = img.naturalWidth;
			originalHeight = img.naturalHeight;
			imageLoaded = true;
			if (previewUrl && previewUrl !== url) URL.revokeObjectURL(previewUrl);
			previewUrl = url;
		};
		img.onerror = () => {
			URL.revokeObjectURL(url);
			error = 'Failed to load image.';
		};
		img.src = url;
	}

	async function processResize() {
		if (!selectedFile || isSvg || !imageLoaded) return;

		const img = new Image();
		const url = URL.createObjectURL(selectedFile);

		await new Promise<void>((resolve, reject) => {
			img.onload = () => resolve();
			img.onerror = () => reject();
			img.src = url;
		});

		const newW = Math.round(originalWidth * resizeScale / 100);
		const newH = Math.round(originalHeight * resizeScale / 100);

		const canvas = document.createElement('canvas');
		canvas.width = newW;
		canvas.height = newH;
		const ctx = canvas.getContext('2d')!;
		ctx.imageSmoothingEnabled = true;
		ctx.imageSmoothingQuality = 'high';
		ctx.drawImage(img, 0, 0, newW, newH);

		const outputType = selectedFile.type === 'image/png' ? 'image/png'
			: selectedFile.type === 'image/webp' ? 'image/webp'
			: 'image/jpeg';
		const quality = outputType === 'image/png' ? undefined : 0.9;

		const blob = await new Promise<Blob>((resolve) => {
			canvas.toBlob((b) => resolve(b!), outputType, quality);
		});

		resizedBlob = blob;
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		previewUrl = URL.createObjectURL(blob);
		URL.revokeObjectURL(url);
	}

	function handleUpload() {
		if (!selectedFile) return;
		const fileToUpload = isSvg || !resizedBlob
			? selectedFile
			: new File([resizedBlob], selectedFile.name, { type: resizedBlob.type });
		dispatch('upload', fileToUpload);
	}

	function clearSelection() {
		selectedFile = null;
		resizedBlob = null;
		isSvg = false;
		imageLoaded = false;
		error = null;
		resizeScale = 100;
		if (previewUrl) {
			URL.revokeObjectURL(previewUrl);
			previewUrl = null;
		}
		if (fileInput) fileInput.value = '';
	}

	function handleRemove() {
		clearSelection();
		dispatch('remove');
	}

	$: displayUrl = previewUrl || (currentLogoUrl ? mediaUrl(currentLogoUrl) : null);
	$: currentW = Math.round(originalWidth * resizeScale / 100);
	$: currentH = Math.round(originalHeight * resizeScale / 100);
</script>

<div class="space-y-3">
	<!-- Drop zone / Preview area -->
	<button
		type="button"
		class="relative flex w-full items-center justify-center border-2 border-dashed p-6 transition-colors {dragOver ? 'border-primary-400 bg-primary-50' : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'}"
		on:dragover|preventDefault={() => (dragOver = true)}
		on:dragleave={() => (dragOver = false)}
		on:drop|preventDefault={handleDrop}
		on:click={() => fileInput.click()}
	>
		{#if displayUrl}
			<div class="flex flex-col items-center gap-3">
				<img
					src={displayUrl}
					alt="Logo preview"
					class="max-h-24 max-w-[200px] object-contain"
				/>
				<p class="text-xs text-gray-400">Click or drag to replace</p>
			</div>
		{:else}
			<div class="flex flex-col items-center gap-2 text-gray-400">
				<svg class="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
					/>
				</svg>
				<p class="text-sm font-medium text-gray-500">Click or drag to upload</p>
				<p class="text-xs">PNG, JPG, WEBP, or SVG — Max {MAX_SIZE_MB} MB</p>
			</div>
		{/if}
		<input
			bind:this={fileInput}
			type="file"
			accept={ACCEPTED_EXTENSIONS}
			class="hidden"
			on:change={handleFileSelect}
		/>
	</button>

	<!-- Resize controls (raster only) -->
	{#if selectedFile && !isSvg && imageLoaded}
		<div class="border border-gray-200 bg-gray-50 p-4">
			<div class="flex items-center justify-between">
				<label for="resize-slider" class="text-sm font-medium text-gray-700">
					Resize
				</label>
				<span class="text-xs font-medium text-gray-500">
					{currentW} × {currentH} px
					<span class="text-gray-400">({resizeScale}%)</span>
				</span>
			</div>
			<input
				id="resize-slider"
				type="range"
				min="10"
				max="100"
				step="5"
				bind:value={resizeScale}
				on:change={processResize}
				class="mt-2 w-full accent-primary-600"
			/>
			<p class="mt-1 text-[11px] text-gray-400">
				Original: {originalWidth} × {originalHeight} px
			</p>
		</div>
	{/if}

	<!-- SVG info -->
	{#if selectedFile && isSvg}
		<div class="flex items-center gap-2 border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
			<svg class="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			SVG files are vector-based and scale to any size — no resize needed.
		</div>
	{/if}

	<!-- Error -->
	{#if error}
		<div class="flex items-center gap-2 bg-red-50 px-3 py-2 text-sm text-red-600">
			<svg class="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			{error}
		</div>
	{/if}

	<!-- Action buttons -->
	<div class="flex gap-2">
		{#if selectedFile}
			<button
				type="button"
				on:click={handleUpload}
				disabled={uploading}
				class="inline-flex items-center gap-2 bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
			>
				{#if uploading}
					<svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
					</svg>
					Uploading…
				{:else}
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
					</svg>
					Upload Logo
				{/if}
			</button>
			<button
				type="button"
				on:click={clearSelection}
				class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
			>
				Cancel
			</button>
		{/if}
		{#if currentLogoUrl && !selectedFile}
			<button
				type="button"
				on:click={handleRemove}
				class="inline-flex items-center gap-1.5 border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
				</svg>
				Remove Logo
			</button>
		{/if}
	</div>
</div>

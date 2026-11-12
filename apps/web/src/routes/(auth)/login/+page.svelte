<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { t } from 'svelte-i18n';
	import { api, mediaUrl } from '$lib/api/client';
	import { setUser } from '$lib/stores/auth';

	let username = '';
	let password = '';
	let rememberMe = false;
	let showPassword = false;
	let capsLock = false;
	let loading = false;
	let error = '';

	let companyDisplayName = '';
	let companyLogoUrl: string | null = null;
	let usernameInput: HTMLInputElement;

	onMount(async () => {
		usernameInput?.focus();
		try {
			const b = await api.branding();
			companyDisplayName = b.display_name;
			companyLogoUrl = b.logo_url;
		} catch {
			// Branding is decorative; the form stays usable without it.
		}
	});

	/** Caps Lock is a common cause of a failed sign-in — surface it before submit. */
	function trackCapsLock(event: KeyboardEvent) {
		capsLock = event.getModifierState?.('CapsLock') ?? false;
	}

	async function handleSubmit() {
		if (!username || !password || loading) return;
		loading = true;
		error = '';
		try {
			await api.login(username, password, rememberMe);
			setUser(await api.me());
			goto('/dashboard');
		} catch (e) {
			// Deliberately non-specific: never reveal whether the account exists.
			error = e instanceof Error && e.message ? e.message : $t('login.error');
		} finally {
			loading = false;
		}
	}

	$: brandName = companyDisplayName || $t('login.appName');
</script>

<svelte:head>
	<title>{brandName} — {$t('login.signIn')}</title>
</svelte:head>

<div class="auth">
	<!-- Form column -->
	<main class="auth__panel">
		<div class="auth__content">
			<div class="brand">
				{#if companyLogoUrl}
					<img class="brand__logo" src={mediaUrl(companyLogoUrl)} alt="" />
				{/if}
				<span class="brand__name">{brandName}</span>
			</div>

			<div class="heading">
				<h1>{$t('login.title')}</h1>
				<p>{$t('login.subtitle')}</p>
			</div>

			<form on:submit|preventDefault={handleSubmit} novalidate>
				{#if error}
					<div class="alert" role="alert">
						<svg viewBox="0 0 16 16" aria-hidden="true">
							<path
								d="M8 1.5 15 14H1L8 1.5Z M8 6.2v3.4 M8 11.6v.6"
								fill="none"
								stroke="currentColor"
								stroke-width="1.4"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>
						<span>{error}</span>
					</div>
				{/if}

				<div class="field">
					<label for="username">{$t('login.username')}</label>
					<input
						id="username"
						name="username"
						type="text"
						bind:this={usernameInput}
						bind:value={username}
						autocomplete="username"
						autocapitalize="none"
						spellcheck="false"
						aria-invalid={error ? 'true' : undefined}
						required
					/>
				</div>

				<div class="field">
					<label for="password">{$t('login.password')}</label>
					<div class="field__control">
						<input
							id="password"
							name="password"
							type={showPassword ? 'text' : 'password'}
							value={password}
							on:input={(e) => (password = e.currentTarget.value)}
							on:keyup={trackCapsLock}
							on:keydown={trackCapsLock}
							autocomplete="current-password"
							aria-invalid={error ? 'true' : undefined}
							aria-describedby={capsLock ? 'caps-hint' : undefined}
							required
						/>
						<button
							type="button"
							class="reveal"
							on:click={() => (showPassword = !showPassword)}
							aria-label={showPassword ? $t('login.hidePassword') : $t('login.showPassword')}
							aria-pressed={showPassword}
						>
							{showPassword ? $t('login.hide') : $t('login.show')}
						</button>
					</div>
					{#if capsLock}
						<p class="hint" id="caps-hint">{$t('login.capsLock')}</p>
					{/if}
				</div>

				<label class="remember">
					<input type="checkbox" bind:checked={rememberMe} />
					<span>{$t('login.rememberMe')}</span>
				</label>

				<button type="submit" class="submit" disabled={loading}>
					{loading ? $t('login.signingIn') : $t('login.signIn')}
				</button>
			</form>
		</div>
	</main>

	<!-- Brand column: a quiet surface, not an illustration -->
	<aside class="auth__aside" aria-hidden="true">
		<div class="aside__rule"></div>
		<div class="aside__copy">
			<p class="aside__lead">{$t('login.tagline')}</p>
			<p class="aside__sub">{$t('login.taglineSubtitle')}</p>
		</div>
		<p class="aside__mark">{brandName}</p>
	</aside>
</div>

<style>
	/* Palette is the project's own brand scale (tailwind.config.ts `primary`)
	   plus the slate neutrals already used by the authenticated shell. */
	.auth {
		--ink: #031927;
		--accent: #2d5a73;
		--accent-soft: #508aa8;
		--text: #1e293b;
		--muted: #64748b;
		--line: #e2e8f0;
		--field: #ffffff;
		--danger: #ba1200;

		display: grid;
		grid-template-columns: minmax(0, 1fr);
		height: 100%;
		background: #ffffff;
		color: var(--text);
	}

	@media (min-width: 900px) {
		.auth {
			grid-template-columns: minmax(0, 5fr) minmax(0, 4fr);
		}
	}

	/* ── Form column ───────────────────────────────────────── */
	.auth__panel {
		display: flex;
		min-width: 0;
		align-items: center;
		justify-content: center;
		overflow-y: auto;
		padding: 2.5rem 1.25rem;
	}

	@media (min-width: 480px) {
		.auth__panel {
			padding: 3rem 2rem;
		}
	}

	.auth__content {
		width: 100%;
		max-width: 24rem;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		margin-bottom: 3.5rem;
	}

	.brand__logo {
		height: 1.75rem;
		width: auto;
		object-fit: contain;
	}

	.brand__name {
		font-size: 0.9375rem;
		font-weight: 600;
		letter-spacing: -0.01em;
		color: var(--text);
	}

	.heading {
		margin-bottom: 2rem;
	}

	.heading h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 600;
		letter-spacing: -0.021em;
		color: var(--ink);
	}

	.heading p {
		margin: 0.4375rem 0 0;
		font-size: 0.875rem;
		line-height: 1.5;
		color: var(--muted);
	}

	/* ── Fields ────────────────────────────────────────────── */
	.field {
		margin-bottom: 1.125rem;
	}

	.field label {
		display: block;
		margin-bottom: 0.4375rem;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--text);
	}

	.field__control {
		position: relative;
	}

	.field input[type='text'],
	.field input[type='password'] {
		width: 100%;
		height: 2.75rem;
		padding: 0 0.875rem;
		border: 1px solid var(--line);
		border-radius: 6px;
		background: var(--field);
		font: inherit;
		font-size: 0.875rem;
		color: var(--text);
		transition:
			border-color 120ms ease,
			box-shadow 120ms ease;
	}

	/* Must clear the reveal button, including the longer French label.
	   Needs the [type] selectors to outrank the padding shorthand above. */
	.field__control input[type='text'],
	.field__control input[type='password'] {
		padding-right: 5rem;
	}

	.field input::placeholder {
		color: #94a3b8;
	}

	.field input:focus {
		outline: none;
		border-color: var(--accent-soft);
		box-shadow: 0 0 0 3px rgba(80, 138, 168, 0.16);
	}

	.field input[aria-invalid='true'] {
		border-color: var(--danger);
	}

	.reveal {
		position: absolute;
		right: 0.5rem;
		top: 50%;
		transform: translateY(-50%);
		padding: 0.25rem 0.375rem;
		border: 0;
		border-radius: 4px;
		background: transparent;
		font: inherit;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--muted);
		cursor: pointer;
	}

	.reveal:hover {
		color: var(--accent);
	}

	.reveal:focus-visible {
		outline: 2px solid var(--accent-soft);
		outline-offset: 1px;
	}

	.hint {
		margin: 0.4375rem 0 0;
		font-size: 0.75rem;
		color: #92600a;
	}

	/* ── Remember me ───────────────────────────────────────── */
	.remember {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 1.25rem 0 1.5rem;
		font-size: 0.8125rem;
		color: var(--muted);
		cursor: pointer;
		user-select: none;
	}

	.remember input {
		width: 0.9375rem;
		height: 0.9375rem;
		accent-color: var(--accent);
		cursor: pointer;
	}

	.remember input:focus-visible {
		outline: 2px solid var(--accent-soft);
		outline-offset: 2px;
	}

	/* ── Submit ────────────────────────────────────────────── */
	.submit {
		width: 100%;
		height: 2.75rem;
		border: 0;
		border-radius: 6px;
		background: var(--accent);
		font: inherit;
		font-size: 0.875rem;
		font-weight: 500;
		color: #ffffff;
		cursor: pointer;
		transition: background-color 120ms ease;
	}

	.submit:hover:not(:disabled) {
		background: #24485c;
	}

	.submit:focus-visible {
		outline: 2px solid var(--accent-soft);
		outline-offset: 2px;
	}

	.submit:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* ── Error ─────────────────────────────────────────────── */
	.alert {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
		padding: 0.6875rem 0.875rem;
		border-left: 2px solid var(--danger);
		border-radius: 0 4px 4px 0;
		background: #fdf3f2;
		font-size: 0.8125rem;
		line-height: 1.45;
		color: #8f1400;
	}

	.alert svg {
		flex: none;
		width: 1rem;
		height: 1rem;
		margin-top: 0.0625rem;
	}

	/* ── Brand column ──────────────────────────────────────── */
	.auth__aside {
		display: none;
	}

	@media (min-width: 900px) {
		.auth__aside {
			position: relative;
			display: flex;
			flex-direction: column;
			justify-content: flex-end;
			padding: 3.5rem;
			overflow: hidden;
			background-color: var(--ink);
			/* Drafting hairlines — a measured surface, not a picture. */
			background-image:
				linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
				linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
			background-size: 88px 88px;
			background-position: center;
		}
	}

	.aside__rule {
		width: 2rem;
		height: 2px;
		margin-bottom: 1.75rem;
		background: var(--accent-soft);
	}

	.aside__copy {
		max-width: 26rem;
	}

	.aside__lead {
		margin: 0;
		font-size: 1.375rem;
		font-weight: 500;
		line-height: 1.35;
		letter-spacing: -0.017em;
		color: #ffffff;
	}

	.aside__sub {
		margin: 0.75rem 0 0;
		font-size: 0.875rem;
		line-height: 1.6;
		color: rgba(255, 255, 255, 0.62);
	}

	.aside__mark {
		margin: 3.5rem 0 0;
		font-size: 0.75rem;
		font-weight: 500;
		letter-spacing: 0.09em;
		text-transform: uppercase;
		color: rgba(255, 255, 255, 0.34);
	}

	@media (prefers-reduced-motion: reduce) {
		.field input,
		.submit {
			transition: none;
		}
	}
</style>

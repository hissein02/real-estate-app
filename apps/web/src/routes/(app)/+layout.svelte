<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { t } from 'svelte-i18n';
	import { api, mediaUrl } from '$lib/api/client';
	import { currentUser, setUser, companyInfo, setCompanyInfo } from '$lib/stores/auth';

	let collapsed = false;

	onMount(async () => {
		const stored = localStorage.getItem('sidebar-collapsed');
		if (stored !== null) collapsed = stored === 'true';
		try {
			const [user, company] = await Promise.all([api.me(), api.settings.getCompany()]);
			setUser(user);
			setCompanyInfo(company);
		} catch {
			goto('/login');
		}
	});

	function toggleSidebar() {
		collapsed = !collapsed;
		localStorage.setItem('sidebar-collapsed', String(collapsed));
	}

	async function logout() {
		try {
			await api.logout();
		} catch {}
		setUser(null);
		goto('/login');
	}

	const navSections = [
		{
			labelKey: 'nav.overview',
			items: [
				{
					href: '/dashboard',
					labelKey: 'nav.dashboard',
					icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6'
				},
				{
					href: '/schedule',
					labelKey: 'nav.schedule',
					icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z'
				}
			]
		},
		{
			labelKey: 'nav.finance',
			items: [
				{
					href: '/billing/invoices',
					labelKey: 'nav.invoices',
					icon: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z'
				},
				{
					href: '/billing/payments',
					labelKey: 'nav.payments',
					icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z'
				}
			]
		},
		{
			labelKey: 'nav.portfolio',
			items: [
				{
					href: '/owners',
					labelKey: 'nav.owners',
					icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z'
				},
				{
					href: '/properties',
					labelKey: 'nav.properties',
					icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4'
				},
				{
					href: '/units',
					labelKey: 'nav.units',
					icon: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z'
				},
				{
					href: '/tenants',
					labelKey: 'nav.tenants',
					icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
				},
				{
					href: '/leases',
					labelKey: 'nav.leases',
					icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
				}
			]
		},
		{
			labelKey: 'nav.analytics',
			items: [
				{
					href: '/reports',
					labelKey: 'nav.reports',
					icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'
				}
			]
		}
	];

	const adminItem = {
		href: '/admin',
		labelKey: 'nav.admin',
		icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z'
	};

	$: currentPath = $page.url.pathname;
</script>

<svelte:head>
	<title>{$companyInfo?.display_name || $t('common.appName')}</title>
</svelte:head>

<div class="app-shell">
	<!-- Sidebar -->
	<aside class="sidebar" class:sidebar--collapsed={collapsed}>

		<!-- Brand -->
		<div class="brand">
			{#if !collapsed}
				<div class="brand-logo">
					{#if $companyInfo?.logo_url}
						<img src={mediaUrl($companyInfo.logo_url)} alt="logo" class="logo-img" />
					{:else}
						<div class="logo-icon">
							<svg class="icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
							</svg>
						</div>
					{/if}
				</div>
				<span class="brand-name">{$companyInfo?.display_name || 'RealEstate'}</span>
				<button class="collapse-btn" on:click={toggleSidebar} title={$t('common.close')}>
					<svg class="icon-xs" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</button>
			{:else}
				<button class="expand-btn" on:click={toggleSidebar} title={$t('nav.overview')}>
					{#if $companyInfo?.logo_url}
						<img src={mediaUrl($companyInfo.logo_url)} alt="logo" class="logo-img-sm" />
					{:else}
						<div class="logo-icon-sm">
							<svg class="icon-xs" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
							</svg>
						</div>
					{/if}
				</button>
			{/if}
		</div>

		<!-- Navigation -->
		<nav class="nav">
			{#each navSections as section}
				<div class="nav-section">
					{#if !collapsed}
						<p class="section-label">{$t(section.labelKey)}</p>
					{/if}
					{#each section.items as item}
						{@const active = currentPath.startsWith(item.href)}
						<a href={item.href} class="nav-link" class:active title={collapsed ? $t(item.labelKey) : ''}>
							<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d={item.icon} />
							</svg>
							{#if !collapsed}<span>{$t(item.labelKey)}</span>{/if}
						</a>
					{/each}
				</div>
			{/each}

			{#if $currentUser?.role === 'admin'}
				{@const active = currentPath.startsWith(adminItem.href)}
				<div class="nav-section">
					{#if !collapsed}<p class="section-label">{$t('nav.settings')}</p>{/if}
					<a href={adminItem.href} class="nav-link" class:active title={collapsed ? $t(adminItem.labelKey) : ''}>
						<svg class="nav-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d={adminItem.icon} />
						</svg>
						{#if !collapsed}<span>{$t(adminItem.labelKey)}</span>{/if}
					</a>
				</div>
			{/if}
		</nav>

		<!-- User -->
		<div class="user-area">
			{#if $currentUser}
				<div class="avatar">
					{$currentUser.first_name?.[0] ?? $currentUser.username[0].toUpperCase()}
				</div>
				{#if !collapsed}
					<div class="user-info">
						<span class="user-name">{$currentUser.first_name} {$currentUser.last_name}</span>
						<span class="user-role">{$currentUser.role.replace('_', ' ')}</span>
					</div>
					<button class="logout-btn" on:click={logout} title={$t('common.signOut')}>
						<svg class="icon-xs" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
						</svg>
					</button>
				{:else}
					<button class="logout-btn logout-btn--stacked" on:click={logout} title={$t('common.signOut')}>
						<svg class="icon-xs" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
						</svg>
					</button>
				{/if}
			{/if}
		</div>
	</aside>

	<!-- Content -->
	<main class="main">
		<slot />
	</main>
</div>

<style>
	.app-shell {
		display: flex;
		height: 100vh;
		background: #f8fafc;
	}

	/* ── Sidebar ── */
	.sidebar {
		display: flex;
		flex-direction: column;
		width: 220px;
		flex-shrink: 0;
		background: #ffffff;
		border-right: 1px solid #e2e8f0;
		transition: width 0.2s ease;
		overflow: hidden;
	}

	.sidebar--collapsed {
		width: 56px;
	}

	/* ── Brand ── */
	.brand {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 56px;
		padding: 0 12px;
		border-bottom: 1px solid #f1f5f9;
		flex-shrink: 0;
	}

	.brand-logo { flex-shrink: 0; }

	.logo-icon {
		width: 30px;
		height: 30px;
		border-radius: 2px;
		background: #ba1200;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
		flex-shrink: 0;
	}

	.logo-img {
		width: 30px;
		height: 30px;
		border-radius: 2px;
		object-fit: contain;
	}

	.brand-name {
		flex: 1;
		font-size: 0.8125rem;
		font-weight: 700;
		color: #0f172a;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		letter-spacing: -0.01em;
	}

	.collapse-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		border-radius: 2px;
		border: none;
		background: transparent;
		color: #94a3b8;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.12s, color 0.12s;
	}

	.collapse-btn:hover {
		background: #f1f5f9;
		color: #475569;
	}

	/* Collapsed: clicking logo expands */
	.expand-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		height: 100%;
		border: none;
		background: transparent;
		cursor: pointer;
		padding: 0;
	}

	.logo-icon-sm {
		width: 30px;
		height: 30px;
		border-radius: 2px;
		background: #ba1200;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
	}

	.logo-img-sm {
		width: 30px;
		height: 30px;
		border-radius: 2px;
		object-fit: contain;
	}

	/* ── Navigation ── */
	.nav {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		padding: 8px 0;
	}

	.nav::-webkit-scrollbar { width: 0; }

	.nav-section {
		padding: 0 8px;
		margin-bottom: 2px;
	}

	.section-label {
		font-size: 0.625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #94a3b8;
		padding: 10px 8px 4px;
		margin: 0;
	}

	.nav-link {
		display: flex;
		align-items: center;
		gap: 9px;
		padding: 7px 8px;
		border-radius: 2px;
		text-decoration: none;
		font-size: 0.8125rem;
		font-weight: 500;
		color: #64748b;
		white-space: nowrap;
		overflow: hidden;
		transition: background 0.1s, color 0.1s;
		position: relative;
	}

	.nav-link:hover {
		background: #f8fafc;
		color: #1e293b;
	}

	.nav-link.active {
		background: #f0f7fb;
		color: #031927;
		font-weight: 600;
	}

	/* Active left accent — doesn't shift content */
	.nav-link.active::before {
		content: '';
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 3px;
		height: 16px;
		background: #508aa8;
	}

	/* Collapsed nav */
	.sidebar--collapsed .nav-section {
		padding: 0 4px;
	}

	.sidebar--collapsed .nav-link {
		justify-content: center;
		padding: 9px 0;
	}

	.sidebar--collapsed .nav-link.active::before {
		height: 20px;
	}

	.nav-icon {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
	}

	/* ── User area ── */
	.user-area {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-top: 1px solid #f1f5f9;
		flex-shrink: 0;
	}

	.sidebar--collapsed .user-area {
		flex-direction: column;
		padding: 8px 4px;
		gap: 6px;
	}

	.avatar {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: #508aa8;
		color: #fff;
		font-size: 0.6875rem;
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.user-info {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.user-name {
		font-size: 0.75rem;
		font-weight: 600;
		color: #1e293b;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.user-role {
		font-size: 0.625rem;
		color: #94a3b8;
		text-transform: capitalize;
		white-space: nowrap;
	}

	.logout-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 26px;
		height: 26px;
		border-radius: 2px;
		border: none;
		background: transparent;
		color: #94a3b8;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.12s, color 0.12s;
	}

	.logout-btn:hover {
		background: #fee2e2;
		color: #dc2626;
	}

	.logout-btn--stacked {
		width: 32px;
		height: 28px;
	}

	/* ── Icons ── */
	.icon-xs {
		width: 14px;
		height: 14px;
	}

	.icon-sm {
		width: 16px;
		height: 16px;
	}

	/* ── Main ── */
	.main {
		flex: 1;
		overflow-y: auto;
		padding: 1.5rem;
		min-width: 0;
	}
</style>

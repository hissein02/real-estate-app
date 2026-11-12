<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { t, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { api } from '$lib/api/client';
	import { formatCurrency } from '$lib/utils/format';
	import type { DashboardKPI } from '$lib/api/types';
	import Spinner from '$lib/components/Spinner.svelte';

	// ── State ────────────────────────────────────────────────────────────────
	let kpi: DashboardKPI | null = null;
	let loading = true;
	let error = '';
	let viewMode: 'month' | 'year' = 'month';

	// Chart DOM refs
	let monthRevenueEl: HTMLDivElement;
	let yearRevenueEl: HTMLDivElement;
	let yearRevenueDonutEl: HTMLDivElement;
	let invoiceDonutEl: HTMLDivElement;

	let charts: any[] = [];

	// ── Color palette ────────────────────────────────────────────────────────
	const C = {
		brickEmber: '#ba1200',
		inkBlack: '#031927',
		babyBlue: '#9dd1f1',
		airForce: '#508aa8',
		paleSky: '#c8e0f4',
	};

	// ── Status semantic colors (matching schedule page) ───────────────────
	const STATUS_COLORS = {
		paid:     '#16a34a',  // green
		partial:  '#ea580c',  // orange
		overdue:  '#dc2626',  // red
		issued:   '#ca8a04',  // yellow/amber
		upcoming: '#94a3b8',  // grey
	};

	// ── Helpers ──────────────────────────────────────────────────────────────
	const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

	const now = new Date();
	const currentYear = now.getFullYear();
	const currentMonthName = MONTHS_SHORT[now.getMonth()];

	function fmt(val: string | number, currency = 'XAF'): string {
		return formatCurrency(val, currency);
	}

	function fmtShort(n: number): string {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
		return n.toString();
	}

	$: yearCollected = kpi ? kpi.year_trend.reduce((s, p) => s + parseFloat(p.actual), 0) : 0;
	$: yearInvoiced  = kpi ? kpi.year_trend.reduce((s, p) => s + parseFloat(p.expected), 0) : 0;

	function methodLabel(method: string): string {
		const T = get(t);
		const labels: Record<string, string> = {
			cash: T('payments.cash'),
			bank_transfer: T('payments.bank_transfer'),
			check: T('payments.cheque'),
			mobile_money: T('payments.mobile_money'),
			other: T('payments.other'),
		};
		return labels[method] || method;
	}

	function statusConfig(status: string, isOverdue: boolean): { label: string; bg: string; text: string } {
		const T = get(t);
		if (isOverdue) return { label: T('status.periodStatus.overdue'), bg: '#fef2f2', text: C.brickEmber };
		switch (status) {
			case 'paid': return { label: T('status.periodStatus.paid'), bg: '#f0fdf4', text: '#16a34a' };
			case 'partially_paid': return { label: T('status.invoice.partially_paid'), bg: '#eff6ff', text: C.airForce };
			case 'issued': return { label: T('status.periodStatus.issued'), bg: '#fefce8', text: '#ca8a04' };
			default: return { label: status, bg: '#f9fafb', text: '#6b7280' };
		}
	}

	function initials(name: string): string {
		return name
			.split(' ')
			.map((p) => p[0])
			.join('')
			.toUpperCase()
			.slice(0, 2);
	}

	// ── Chart rendering ──────────────────────────────────────────────────────
	async function renderMonthCharts(ApexCharts: any) {
		if (!kpi) return;

		const T = get(t);
		const collected = parseFloat(kpi.monthly_collected);
		const outstanding = Math.max(0, parseFloat(kpi.monthly_invoiced) - collected);
		const total = collected + outstanding;

		if (monthRevenueEl) {
			const monthChart = new ApexCharts(monthRevenueEl, {
				chart: {
					type: 'donut',
					height: 260,
					fontFamily: 'inherit',
				},
				series: total > 0 ? [collected, outstanding] : [1],
				labels: total > 0 ? [T('dashboard.collected'), T('dashboard.outstanding')] : [T('dashboard.noDataAvailable')],
				colors: total > 0 ? [STATUS_COLORS.paid, STATUS_COLORS.overdue] : ['#e5e7eb'],
				plotOptions: {
					pie: {
						donut: {
							size: '74%',
							labels: {
								show: true,
								name: {
									fontSize: '13px',
									color: '#6b7280',
									offsetY: -4,
								},
								value: {
									fontSize: '22px',
									fontWeight: 700,
									color: C.inkBlack,
									offsetY: 4,
									formatter: (val: string) => fmtShort(parseFloat(val)),
								},
								total: {
									show: true,
									label: T('reports.collectionRate'),
									fontSize: '11px',
									color: '#9ca3af',
									formatter: () => `${kpi!.collection_rate}%`,
								},
							},
						},
					},
				},
				dataLabels: { enabled: false },
				stroke: { width: 0 },
				legend: {
					position: 'bottom',
					fontSize: '12px',
					labels: { colors: '#6b7280' },
					markers: { size: 7, offsetX: -2 },
				},
				tooltip: {
					y: { formatter: (val: number) => fmt(val) },
				},
			});
			monthChart.render();
			charts.push(monthChart);
		}
	}

	async function renderYearCharts(ApexCharts: any) {
		if (!kpi) return;

		const T = get(t);

		// --- Stacked bar: Collected + Outstanding per month ---
		if (yearRevenueEl) {
			const actualVals = kpi.year_trend.map((p) => parseFloat(p.actual));
			const outstandingVals = kpi.year_trend.map((p) =>
				Math.max(0, parseFloat(p.expected) - parseFloat(p.actual))
			);

			const yearBar = new ApexCharts(yearRevenueEl, {
				chart: {
					type: 'bar',
					stacked: true,
					height: 280,
					fontFamily: 'inherit',
					toolbar: { show: false },
				},
				series: [
					{ name: T('dashboard.collected'), data: actualVals },
					{ name: T('dashboard.outstanding'), data: outstandingVals },
				],
				colors: [STATUS_COLORS.paid, STATUS_COLORS.overdue],
				xaxis: {
					categories: MONTHS_SHORT,
					axisBorder: { show: false },
					axisTicks: { show: false },
					labels: { style: { fontSize: '11px', colors: '#9ca3af' } },
				},
				yaxis: {
					labels: {
						style: { fontSize: '11px', colors: '#9ca3af' },
						formatter: fmtShort,
					},
				},
				dataLabels: { enabled: false },
				grid: {
					borderColor: '#f3f4f6',
					strokeDashArray: 4,
					padding: { left: 4, right: 4 },
				},
				plotOptions: {
					bar: {
						borderRadius: 4,
						borderRadiusWhenStacked: 'last',
						columnWidth: '52%',
					},
				},
				legend: {
					position: 'top',
					horizontalAlign: 'right',
					fontSize: '12px',
					labels: { colors: '#6b7280' },
					markers: { size: 7, offsetX: -2 },
				},
				stroke: { width: 0 },
				tooltip: {
					y: { formatter: (val: number) => fmt(val) },
				},
			});
			yearBar.render();
			charts.push(yearBar);
		}

		// --- Yearly Revenue Donut ---
		if (yearRevenueDonutEl) {
			const yCollected = kpi.year_trend.reduce((s, p) => s + parseFloat(p.actual), 0);
			const yInvoiced  = kpi.year_trend.reduce((s, p) => s + parseFloat(p.expected), 0);
			const yOutstanding = Math.max(0, yInvoiced - yCollected);
			const yTotal = yCollected + yOutstanding;
			const yRate = yInvoiced > 0 ? Math.round((yCollected / yInvoiced) * 100) : 0;

			const yearDonut = new ApexCharts(yearRevenueDonutEl, {
				chart: { type: 'donut', height: 260, fontFamily: 'inherit' },
				series: yTotal > 0 ? [yCollected, yOutstanding] : [1],
				labels: yTotal > 0 ? [T('dashboard.collected'), T('dashboard.outstanding')] : [T('dashboard.noDataAvailable')],
				colors: yTotal > 0 ? [STATUS_COLORS.paid, STATUS_COLORS.overdue] : ['#e5e7eb'],
				plotOptions: {
					pie: {
						donut: {
							size: '74%',
							labels: {
								show: true,
								name: { fontSize: '13px', color: '#6b7280', offsetY: -4 },
								value: {
									fontSize: '22px', fontWeight: 700, color: C.inkBlack, offsetY: 4,
									formatter: (val: string) => fmtShort(parseFloat(val)),
								},
								total: {
									show: true, label: T('reports.collectionRate'),
									fontSize: '11px', color: '#9ca3af',
									formatter: () => `${yRate}%`,
								},
							},
						},
					},
				},
				dataLabels: { enabled: false },
				stroke: { width: 0 },
				legend: {
					position: 'bottom', fontSize: '12px',
					labels: { colors: '#6b7280' }, markers: { size: 7, offsetX: -2 },
				},
				tooltip: { y: { formatter: (val: number) => fmt(val) } },
			});
			yearDonut.render();
			charts.push(yearDonut);
		}

		// --- Invoice Status Donut ---
		if (invoiceDonutEl) {
			const statuses = kpi.invoice_statuses;
			const slices = [
				{ label: T('status.periodStatus.paid'), value: statuses.paid, color: STATUS_COLORS.paid },
				{ label: T('status.invoice.issued'), value: statuses.issued, color: STATUS_COLORS.issued },
				{ label: T('status.invoice.partially_paid'), value: statuses.partially_paid, color: STATUS_COLORS.partial },
				{ label: T('status.periodStatus.overdue'), value: statuses.overdue, color: STATUS_COLORS.overdue },
				{ label: T('status.invoice.draft'), value: statuses.draft, color: STATUS_COLORS.upcoming },
			].filter((s) => s.value > 0);

			const invoiceChart = new ApexCharts(invoiceDonutEl, {
				chart: { type: 'donut', height: 260, fontFamily: 'inherit' },
				series: slices.map((s) => s.value),
				labels: slices.map((s) => s.label),
				colors: slices.map((s) => s.color),
				plotOptions: {
					pie: {
						donut: {
							size: '70%',
							labels: {
								show: true,
								name: { fontSize: '12px', color: '#6b7280', offsetY: -4 },
								value: { fontSize: '20px', fontWeight: 700, color: C.inkBlack, offsetY: 4 },
								total: {
									show: true,
									label: T('common.total'),
									fontSize: '11px',
									color: '#9ca3af',
									formatter: (w: any) =>
										w.globals.seriesTotals.reduce((a: number, b: number) => a + b, 0).toString(),
								},
							},
						},
					},
				},
				dataLabels: { enabled: false },
				stroke: { width: 0 },
				legend: {
					position: 'bottom',
					fontSize: '12px',
					labels: { colors: '#6b7280' },
					markers: { size: 7, offsetX: -2 },
				},
				tooltip: { y: { formatter: (val: number) => `${val} ${get(t)('dashboard.invoices')}` } },
			});
			invoiceChart.render();
			charts.push(invoiceChart);
		}

	}

	async function renderCharts() {
		if (!kpi) return;
		const ApexCharts = (await import('apexcharts')).default;
		charts.forEach((c) => c.destroy());
		charts = [];

		if (viewMode === 'month') {
			await renderMonthCharts(ApexCharts);
		} else {
			await renderYearCharts(ApexCharts);
		}
	}

	async function setView(v: 'month' | 'year') {
		if (v === viewMode) return;
		viewMode = v;
		charts.forEach((c) => c.destroy());
		charts = [];
		const { tick } = await import('svelte');
		await tick();
		await renderCharts();
	}

	// ── Lifecycle ────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			kpi = await api.reports.dashboard();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load dashboard';
		} finally {
			loading = false;
		}
	});

	$: if ($locale && !loading && kpi && typeof window !== 'undefined') {
		import('svelte').then(({ tick }) => tick()).then(renderCharts);
	}

	onDestroy(() => {
		charts.forEach((c) => c.destroy());
		charts = [];
	});
</script>

<svelte:head><title>{$t('dashboard.title')} – RealEstate</title></svelte:head>

<div class="space-y-5">

	<!-- ── Hero Header ─────────────────────────────────────────────────────── -->
	<div class="px-6 py-5 flex items-center justify-between" style="background: {C.inkBlack}">
		<div>
			<h1 class="text-xl font-bold text-white tracking-tight">{$t('dashboard.title')}</h1>
			<p class="text-sm mt-0.5" style="color: {C.babyBlue}">
				{#if viewMode === 'month'}
					{currentMonthName} {currentYear} — {$t('dashboard.monthlyView')}
				{:else}
					{currentYear} — {$t('dashboard.annualView')}
				{/if}
			</p>
		</div>
		<!-- View toggle -->
		<div class="flex p-1 gap-1" style="background: rgba(255,255,255,0.1)">
			<button
				class="px-4 py-1.5 text-sm font-medium transition-all duration-150"
				style={viewMode === 'month'
					? 'background: #fff; color: ' + C.inkBlack
					: 'background: transparent; color: rgba(255,255,255,0.7)'}
				on:click={() => setView('month')}
			>{$t('dashboard.monthlyView')}</button>
			<button
				class="px-4 py-1.5 text-sm font-medium transition-all duration-150"
				style={viewMode === 'year'
					? 'background: #fff; color: ' + C.inkBlack
					: 'background: transparent; color: rgba(255,255,255,0.7)'}
				on:click={() => setView('year')}
			>{$t('dashboard.annualView')}</button>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center py-16"><Spinner size="lg" /></div>
	{:else if error}
		<div class="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
	{:else if kpi}

		<!-- ── KPI Strip ──────────────────────────────────────────────────────── -->
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">

			<!-- Collected Revenue -->
			<div class="bg-white p-4 border border-gray-100" style="border-top: 3px solid {STATUS_COLORS.paid}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.collected')}</p>
				<p class="text-lg font-bold mt-1 truncate" style="color: {C.inkBlack}">
					{viewMode === 'year' ? fmt(yearCollected) : fmt(kpi.monthly_collected)}
				</p>
				<p class="text-[11px] text-gray-400 mt-1">
					{$t('common.of')} {viewMode === 'year' ? fmt(yearInvoiced) : fmt(kpi.monthly_invoiced)} {$t('dashboard.invoiced')}
				</p>
			</div>

			<!-- Active Leases -->
			<div class="bg-white p-4 border border-gray-100" style="border-top: 3px solid {C.airForce}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.activeLeases')}</p>
				<p class="text-2xl font-bold mt-1" style="color: {C.inkBlack}">{kpi.active_leases}</p>
				{#if kpi.expiring_30d > 0}
						<p class="text-[11px] font-medium mt-1" style="color: {C.brickEmber}">{kpi.expiring_30d} {$t('dashboard.expiringSoon')}</p>
				{:else}
						<p class="text-[11px] text-gray-400 mt-1">{$t('dashboard.noneExpiringSoon')}</p>
				{/if}
			</div>

			<!-- Occupancy -->
			<div class="bg-white p-4 border border-gray-100" style="border-top: 3px solid {C.airForce}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.occupancy')}</p>
				<p class="text-2xl font-bold mt-1" style="color: {C.inkBlack}">{kpi.occupancy_rate}%</p>
					<p class="text-[11px] text-gray-400 mt-1">{kpi.occupied_units} / {kpi.total_units} {$t('dashboard.ofUnits')}</p>
			</div>

			<!-- Overdue Invoices -->
			<div class="bg-white p-4 border border-gray-100"
				style="border-top: 3px solid {kpi.overdue_invoice_count > 0 ? C.brickEmber : C.paleSky}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.overdue')}</p>
				<p class="text-2xl font-bold mt-1"
					style="color: {kpi.overdue_invoice_count > 0 ? C.brickEmber : C.inkBlack}">
					{kpi.overdue_invoice_count}
				</p>
				<p class="text-[11px] text-gray-400 mt-1">{$t('dashboard.invoices')}</p>
			</div>

			<!-- Properties -->
			<div class="bg-white p-4 border border-gray-100" style="border-top: 3px solid {C.inkBlack}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.properties')}</p>
				<p class="text-2xl font-bold mt-1" style="color: {C.inkBlack}">{kpi.property_count}</p>
					<p class="text-[11px] text-gray-400 mt-1">{$t('dashboard.inPortfolio')}</p>
			</div>

			<!-- Tenants -->
			<div class="bg-white p-4 border border-gray-100" style="border-top: 3px solid {C.babyBlue}">
				<p class="text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.tenants')}</p>
				<p class="text-2xl font-bold mt-1" style="color: {C.inkBlack}">{kpi.tenant_count}</p>
				<p class="text-[11px] text-gray-400 mt-1">{$t('common.active')}</p>
			</div>

		</div>

		<!-- ═══════════════════════════════════════════════════════════════════ -->
		<!-- MONTH VIEW                                                         -->
		<!-- ═══════════════════════════════════════════════════════════════════ -->
		{#if viewMode === 'month'}

			<!-- Revenue Doughnut -->
			<div class="bg-white p-5 border border-gray-100">
					<div class="flex items-start justify-between mb-1">
						<div>
							<h2 class="text-sm font-bold uppercase tracking-widest" style="color: {C.inkBlack}">{$t('dashboard.collected')} vs {$t('dashboard.outstanding')}</h2>
							<p class="text-xs text-gray-400 mt-0.5">{$t('dashboard.revenueVsOutstanding')} — {currentMonthName} {currentYear}</p>
						</div>
					</div>
					{#if parseFloat(kpi.monthly_invoiced) === 0}
						<div class="flex flex-col items-center justify-center h-52 gap-2">
							<div class="w-12 h-12 rounded-full flex items-center justify-center" style="background: {C.paleSky}">
								<svg class="w-6 h-6" style="color: {C.airForce}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
								</svg>
							</div>
							<p class="text-sm text-gray-400">{$t('dashboard.noDataAvailable')}</p>
						</div>
					{:else}
						<div bind:this={monthRevenueEl}></div>
					{/if}
			</div>

			<!-- Tenant Payments Table -->
			<div class="bg-white border border-gray-100 overflow-hidden">
				<div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
					<div>
						<h2 class="text-sm font-bold uppercase tracking-widest" style="color: {C.inkBlack}">{$t('dashboard.tenantPayments')}</h2>
							<p class="text-xs text-gray-400 mt-0.5">{currentMonthName} {currentYear} — {$t('dashboard.invoicesCount', { values: { count: kpi.month_tenants.length } })}</p>
					</div>
					{#if kpi.month_tenants.filter(t => t.is_overdue).length > 0}
						<span class="text-xs font-semibold px-2 py-0.5" style="background: #fef2f2; color: {C.brickEmber}">
							{kpi.month_tenants.filter(t => t.is_overdue).length} {$t('dashboard.overdue')}
						</span>
					{/if}
				</div>

				{#if kpi.month_tenants.length === 0}
					<div class="flex flex-col items-center justify-center py-12 gap-2">
						<div class="w-10 h-10 rounded-full flex items-center justify-center" style="background: {C.paleSky}">
							<svg class="w-5 h-5" style="color: {C.airForce}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
							</svg>
						</div>
						<p class="text-sm text-gray-400">{$t('dashboard.noDataAvailable')}</p>
					</div>
				{:else}
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b border-gray-100">
									<th class="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.tenant')}</th>
									<th class="text-left px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400 hidden sm:table-cell">{$t('dashboard.properties')} / {$t('dashboard.unit')}</th>
									<th class="text-left px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400 hidden md:table-cell">{$t('invoices.invoiceNumber')}</th>
									<th class="text-right px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('common.amount')}</th>
									<th class="text-right px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400 hidden sm:table-cell">{$t('common.paid')}</th>
									<th class="text-right px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400 hidden md:table-cell">{$t('common.balance')}</th>
									<th class="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('common.status')}</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-50">
								{#each kpi.month_tenants as tn}
									{@const sc = statusConfig(tn.status, tn.is_overdue)}
									<tr class="hover:bg-gray-50/50 transition-colors">
										<td class="px-5 py-3.5">
											<div class="flex items-center gap-3">
												<div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
													style="background: {tn.is_overdue ? C.brickEmber : tn.status === 'paid' ? '#16a34a' : C.airForce}">
													{initials(tn.tenant)}
												</div>
												<span class="font-medium text-gray-800 truncate max-w-[120px]">{tn.tenant}</span>
											</div>
										</td>
										<td class="px-4 py-3.5 hidden sm:table-cell">
											<p class="text-gray-700 text-xs font-medium">{tn.property}</p>
											<p class="text-gray-400 text-xs">{tn.unit}</p>
										</td>
										<td class="px-4 py-3.5 hidden md:table-cell">
											<p class="text-gray-500 text-xs font-mono">{tn.invoice_number}</p>
											<p class="text-gray-400 text-xs">{$t('schedule.dueDate')} {tn.due_date}</p>
										</td>
										<td class="px-4 py-3.5 text-right">
											<span class="font-semibold text-gray-800">{fmt(tn.amount, tn.currency)}</span>
										</td>
										<td class="px-4 py-3.5 text-right hidden sm:table-cell">
											<span class="text-sm font-medium" style="color: {C.airForce}">{fmt(tn.paid, tn.currency)}</span>
										</td>
										<td class="px-4 py-3.5 text-right hidden md:table-cell">
											<span class="text-sm font-medium" style="color: {parseFloat(tn.balance) > 0 ? C.brickEmber : '#6b7280'}">{fmt(tn.balance, tn.currency)}</span>
										</td>
										<td class="px-5 py-3.5 text-right">
											<span class="inline-flex items-center px-2.5 py-0.5 text-[11px] font-semibold"
												style="background: {sc.bg}; color: {sc.text}">
												{sc.label}
											</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

		{/if}

		<!-- ═══════════════════════════════════════════════════════════════════ -->
		<!-- YEAR VIEW                                                          -->
		<!-- ═══════════════════════════════════════════════════════════════════ -->
		{#if viewMode === 'year'}

			<!-- Stacked bar chart -->
			<div class="bg-white p-5 border border-gray-100">
				<div class="mb-1">
					<h2 class="text-sm font-bold uppercase tracking-widest" style="color: {C.inkBlack}">{$t('reports.revenue')} — {currentYear}</h2>
						<p class="text-xs text-gray-400 mt-0.5">{$t('dashboard.monthlyCollectedSubtitle')}</p>
				</div>
				<div bind:this={yearRevenueEl}></div>
			</div>

			<!-- Donuts: Annual Revenue + Invoice Status -->
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<!-- Annual Revenue Donut -->
				<div class="bg-white p-5 border border-gray-100">
					<h2 class="text-sm font-bold uppercase tracking-widest mb-1" style="color: {C.inkBlack}">{$t('dashboard.annualRevenue')}</h2>
						<p class="text-xs text-gray-400 mb-3">{$t('dashboard.collectedVsOutstanding')} — {currentYear}</p>
					<div bind:this={yearRevenueDonutEl}></div>
				</div>
				<!-- Invoice Status -->
				<div class="bg-white p-5 border border-gray-100">
					<h2 class="text-sm font-bold uppercase tracking-widest mb-1" style="color: {C.inkBlack}">{$t('dashboard.invoiceStatus')}</h2>
						<p class="text-xs text-gray-400 mb-3">{$t('dashboard.distributionAllInvoices')}</p>
					<div bind:this={invoiceDonutEl}></div>
				</div>
			</div>

			<!-- Top Properties -->
			{#if kpi.top_properties.length > 0}
				<div class="bg-white border border-gray-100 overflow-hidden">
					<div class="px-5 py-4 border-b border-gray-50">
						<h2 class="text-sm font-bold uppercase tracking-widest" style="color: {C.inkBlack}">{$t('dashboard.topProperties')}</h2>
							<p class="text-xs text-gray-400 mt-0.5">{$t('dashboard.byRevenueCollected')}</p>
					</div>
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b border-gray-100">
									<th class="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.propertyName')}</th>
									<th class="text-right px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.revenue')}</th>
									<th class="text-right px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400 hidden sm:table-cell">{$t('properties.units')}</th>
									<th class="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">{$t('dashboard.occupancy')}</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-50">
								{#each kpi.top_properties as prop, i}
									{@const occ = prop.total_units > 0 ? Math.round((prop.occupied_units / prop.total_units) * 100) : 0}
									<tr class="hover:bg-gray-50/50 transition-colors">
										<td class="px-5 py-3.5">
											<div class="flex items-center gap-3">
												<span class="w-7 h-7 flex items-center justify-center text-xs font-bold text-white shrink-0"
													style="background: {i === 0 ? C.inkBlack : i === 1 ? C.airForce : C.babyBlue}; color: {i >= 2 ? C.inkBlack : 'white'}">
													{i + 1}
												</span>
												<span class="font-medium text-gray-800">{prop.name}</span>
											</div>
										</td>
										<td class="px-4 py-3.5 text-right font-semibold text-gray-800">{fmt(prop.revenue)}</td>
										<td class="px-4 py-3.5 text-right text-gray-500 hidden sm:table-cell">{prop.occupied_units} / {prop.total_units}</td>
										<td class="px-5 py-3.5 text-right">
											<div class="flex items-center justify-end gap-2">
												<div class="w-16 h-1.5 rounded-full bg-gray-100">
													<div class="h-1.5 rounded-full transition-all"
														style="width: {occ}%; background: {C.airForce}"></div>
												</div>
												<span class="text-xs font-semibold text-gray-600 w-8 text-right">{occ}%</span>
											</div>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			{/if}

		{/if}
	{/if}

</div>

<script lang="ts">
  import { onMount } from 'svelte';
  import { t, locale } from 'svelte-i18n';
  import { get } from 'svelte/store';
  import { api } from '$lib/api/client';
  import type { NotificationData, NotificationType, NotificationStatus } from '$lib/api/types';

  // ── State ──────────────────────────────────────────────────
  let notifications: NotificationData[] = [];
  let totalCount = 0;
  let loading = true;
  let error = '';

  // Filters
  let filterType: NotificationType | '' = '';
  let filterStatus: NotificationStatus | '' = '';
  let search = '';
  let searchInput = '';

  // Pagination
  let page = 1;
  const pageSize = 25;
  $: totalPages = Math.ceil(totalCount / pageSize);

  // Expanded row (to show full body)
  let expandedId: number | null = null;

  // ── Load ────────────────────────────────────────────────────
  async function load() {
    loading = true;
    error = '';
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (filterType) params.set('type', filterType);
      if (filterStatus) params.set('status', filterStatus);
      if (search) params.set('search', search);

      const res = await api.notifications.list(params.toString());
      notifications = res.results;
      totalCount = res.count;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load notifications';
    } finally {
      loading = false;
    }
  }

  function applyFilters() {
    page = 1;
    search = searchInput.trim();
    load();
  }

  function clearFilters() {
    filterType = '';
    filterStatus = '';
    search = '';
    searchInput = '';
    page = 1;
    load();
  }

  function goPage(p: number) {
    page = p;
    load();
  }

  onMount(load);

  // ── Helpers ─────────────────────────────────────────────────
  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    const lang = get(locale) ?? 'en';
    return new Intl.DateTimeFormat(lang === 'fr' ? 'fr-FR' : 'en-US', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    }).format(new Date(iso));
  }

  // The type name states what it is; a colour per type adds no information.
  const TYPE_CHIP = 'bg-gray-50 text-gray-700 ring-gray-200';

  const STATUS_COLORS: Record<string, string> = {
    sent:    'bg-green-50 text-green-700 ring-green-200',
    failed:  'bg-red-50 text-red-700 ring-red-200',
    pending: 'bg-gray-50 text-gray-600 ring-gray-200',
  };
</script>

<div class="space-y-4">
  <!-- Hero -->
  <div class="px-6 py-5" style="background: #031927">
    <div class="flex items-center gap-4">
      <a
        href="/admin"
        class="inline-flex items-center justify-center p-1.5 transition-colors hover:bg-white/10"
        aria-label={$t('common.back')}
        style="color: #9dd1f1"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </a>
      <div>
        <h1 class="text-2xl font-bold text-white">{$t('notifications.title')}</h1>
        <p class="mt-1 text-sm" style="color: #9dd1f1">
          {$t('notifications.subtitle')}
        </p>
      </div>
    </div>
  </div>

  <!-- Filter bar -->
  <div class="border border-gray-200 bg-white px-4 py-3">
    <div class="flex flex-wrap items-center gap-2">
      <!-- Search -->
      <div class="relative flex-1 min-w-[180px]">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          bind:value={searchInput}
          placeholder={$t('notifications.search')}
          class="w-full border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          on:keydown={(e) => e.key === 'Enter' && applyFilters()}
        />
      </div>

      <!-- Type filter -->
      <select
        bind:value={filterType}
        class="border border-gray-300 py-2 pl-3 pr-8 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
        on:change={applyFilters}
      >
        <option value="">{$t('notifications.allTypes')}</option>
        <option value="rent_reminder">{$t('notifications.types.rent_reminder')}</option>
        <option value="overdue_notice">{$t('notifications.types.overdue_notice')}</option>
        <option value="lease_expiry_warning">{$t('notifications.types.lease_expiry_warning')}</option>
        <option value="invoice_generated">{$t('notifications.types.invoice_generated')}</option>
        <option value="payment_received">{$t('notifications.types.payment_received')}</option>
      </select>

      <!-- Status filter -->
      <select
        bind:value={filterStatus}
        class="border border-gray-300 py-2 pl-3 pr-8 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
        on:change={applyFilters}
      >
        <option value="">{$t('notifications.allStatuses')}</option>
        <option value="sent">{$t('status.notification.sent')}</option>
        <option value="failed">{$t('status.notification.failed')}</option>
        <option value="pending">{$t('status.notification.pending')}</option>
      </select>

      <button
        type="button"
        on:click={applyFilters}
        class="bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800"
      >
        {$t('common.search')}
      </button>

      {#if filterType || filterStatus || search}
        <button
          type="button"
          on:click={clearFilters}
          class="border border-gray-200 px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-50"
        >
          {$t('common.close')}
        </button>
      {/if}

      <span class="ml-auto text-xs text-gray-400">
        {$t('notifications.emailsCount', { values: { count: totalCount } })}
      </span>
    </div>
  </div>

  <!-- Table -->
  <div class="border border-gray-200 bg-white overflow-hidden">
    {#if loading}
      <div class="flex justify-center py-16">
        <svg class="h-8 w-8 animate-spin text-primary-600" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    {:else if error}
      <div class="flex flex-col items-center py-16 text-center">
        <p class="text-sm text-red-600">{error}</p>
        <button on:click={load} class="mt-3 text-xs text-primary-600 hover:underline">{$t('common.retry')}</button>
      </div>
    {:else if notifications.length === 0}
      <div class="flex flex-col items-center py-16 text-center">
        <p class="text-sm font-medium text-gray-500">{$t('notifications.noNotifications')}</p>
        <p class="mt-1 text-xs text-gray-400">{$t('notifications.noNotificationsDescription')}</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-100 text-sm">
          <thead>
            <tr class="bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th class="px-4 py-3 text-left">{$t('notifications.columns.date')}</th>
              <th class="px-4 py-3 text-left">{$t('notifications.columns.type')}</th>
              <th class="px-4 py-3 text-left">{$t('notifications.columns.recipient')}</th>
              <th class="px-4 py-3 text-left">{$t('notifications.columns.subjectContent')}</th>
              <th class="px-4 py-3 text-left">{$t('notifications.columns.triggeredBy')}</th>
              <th class="px-4 py-3 text-left">{$t('notifications.columns.status')}</th>
              <th class="px-4 py-3 text-left w-8"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            {#each notifications as notif (notif.id)}
              <!-- Main row -->
              <tr
                class="group cursor-pointer transition-colors hover:bg-gray-50"
                on:click={() => (expandedId = expandedId === notif.id ? null : notif.id)}
              >
                <!-- Date -->
                <td class="whitespace-nowrap px-4 py-3 text-xs text-gray-500">
                  {formatDate(notif.created_at)}
                </td>

                <!-- Type badge -->
                <td class="px-4 py-3">
                  <span class="inline-flex items-center px-2 py-0.5 text-xs font-medium ring-1 ring-inset {TYPE_CHIP}">
                    {notif.type_display}
                  </span>
                </td>

                <!-- Recipient -->
                <td class="px-4 py-3">
                  <span class="font-medium text-gray-800">{notif.recipient_email}</span>
                  {#if notif.lease_info}
                    <p class="text-xs text-gray-400">{notif.lease_info.tenant_name} · {notif.lease_info.unit_name}</p>
                  {/if}
                </td>

                <!-- Subject + content preview -->
                <td class="max-w-xs px-4 py-3">
                  <p class="truncate font-medium text-gray-800">{notif.subject || '—'}</p>
                  {#if notif.content}
                    <p class="truncate text-xs text-gray-400">{notif.content}</p>
                  {/if}
                </td>

                <!-- Triggered by -->
                <td class="px-4 py-3">
                  <span class="text-xs text-gray-600">{notif.triggered_by || $t('notifications.system')}</span>
                </td>

                <!-- Status badge -->
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium ring-1 ring-inset {STATUS_COLORS[notif.status] ?? ''}">
                    {notif.status_display}
                  </span>
                </td>

                <!-- Expand chevron -->
                <td class="px-4 py-3 text-gray-300">
                  <svg
                    class="h-4 w-4 transition-transform {expandedId === notif.id ? 'rotate-180' : ''}"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </td>
              </tr>

              <!-- Expanded detail row -->
              {#if expandedId === notif.id}
                <tr class="bg-gray-50/80">
                  <td colspan="7" class="px-6 py-4">
                    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <!-- Left: metadata -->
                      <div class="space-y-2 text-xs text-gray-600">
                        <div class="flex gap-2">
                          <span class="w-28 flex-shrink-0 font-medium text-gray-500">{$t('notifications.detail.sentAt')}</span>
                          <span>{formatDate(notif.sent_at)}</span>
                        </div>
                        <div class="flex gap-2">
                          <span class="w-28 flex-shrink-0 font-medium text-gray-500">{$t('notifications.detail.triggeredBy')}</span>
                          <span>{notif.triggered_by || $t('notifications.system')}</span>
                        </div>
                        {#if notif.lease_info}
                          <div class="flex gap-2">
                            <span class="w-28 flex-shrink-0 font-medium text-gray-500">{$t('notifications.detail.tenant')}</span>
                            <span>{notif.lease_info.tenant_name}</span>
                          </div>
                          <div class="flex gap-2">
                            <span class="w-28 flex-shrink-0 font-medium text-gray-500">{$t('notifications.detail.unit')}</span>
                            <span>{notif.lease_info.unit_name}</span>
                          </div>
                        {/if}
                        {#if notif.error_message}
                          <div class="mt-2 border border-red-200 bg-red-50 p-3">
                            <p class="text-xs font-medium text-red-700">{$t('notifications.detail.error')}</p>
                            <p class="mt-1 font-mono text-xs text-red-600 break-all">{notif.error_message}</p>
                          </div>
                        {/if}
                      </div>

                      <!-- Right: email body preview -->
                      <div>
                        <p class="mb-1.5 text-xs font-medium text-gray-500">{$t('notifications.detail.emailBody')}</p>
                        {#if notif.body}
                          <div class="overflow-hidden border border-gray-200 bg-white" style="max-height: 340px;">
                            <iframe
                              srcdoc={notif.body}
                              title="Email preview"
                              class="w-full border-0"
                              style="height: 340px; pointer-events: none;"
                              sandbox="allow-same-origin"
                            ></iframe>
                          </div>
                        {:else}
                          <p class="text-xs italic text-gray-400">{$t('notifications.detail.noBody')}</p>
                        {/if}
                      </div>
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      {#if totalPages > 1}
        <div class="flex items-center justify-between border-t border-gray-100 px-4 py-3">
          <p class="text-xs text-gray-500">
            {$t('notifications.pageInfo', { values: { page, total: totalPages } })} · {totalCount}
          </p>
          <div class="flex gap-1">
            <button
              type="button"
              on:click={() => goPage(page - 1)}
              disabled={page <= 1}
              class="border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
            >{$t('notifications.prevPage')}</button>
            {#each Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              const half = 3;
              let start = Math.max(1, page - half);
              const end = Math.min(totalPages, start + 6);
              start = Math.max(1, end - 6);
              return start + i;
            }).filter(p => p <= totalPages) as p}
              <button
                type="button"
                on:click={() => goPage(p)}
                class="border px-3 py-1.5 text-xs font-medium transition-colors {p === page ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}"
              >{p}</button>
            {/each}
            <button
              type="button"
              on:click={() => goPage(page + 1)}
              disabled={page >= totalPages}
              class="border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
            >{$t('notifications.nextPage')}</button>
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>

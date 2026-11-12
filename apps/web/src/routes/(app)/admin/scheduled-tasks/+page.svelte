<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import { get } from 'svelte/store';
  import { api } from '$lib/api/client';
  import type { TaskConfig, EmailSettingsData } from '$lib/api/types';

  // ── State ──
  let tasks: TaskConfig[] = [];
  let email: EmailSettingsData = {
    smtp_host: '',
    smtp_port: 587,
    smtp_use_tls: true,
    smtp_username: '',
    smtp_password: '',
    from_name: '',
    from_email: '',
    reply_to_email: '',
    task_timezone: 'Africa/Ndjamena'
  };
  let loadingTasks = true;
  let loadingEmail = true;
  let savingEmail = false;
  let togglingTask: string | null = null;
  let savingTask: string | null = null;

  // Per-task editable time values
  let taskEdits: Record<string, { hour: number; minute: number }> = {};

  // Toast
  let toast: { message: string; type: 'success' | 'error' } | null = null;
  let toastTimeout: ReturnType<typeof setTimeout>;

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast = { message, type };
    toastTimeout = setTimeout(() => (toast = null), 4000);
  }

  // ── Human-readable names ──
  const TASK_LABELS: Record<string, { nameKey: string }> = {
    'generate-invoices-daily': { nameKey: 'scheduledTasks.taskNames.generateInvoices' },
    'generate-late-fees-daily': { nameKey: 'scheduledTasks.taskNames.generateLateFees' },
    'send-rent-reminders-daily': { nameKey: 'scheduledTasks.taskNames.rentReminders' },
    'send-lease-expiry-warnings-daily': { nameKey: 'scheduledTasks.taskNames.leaseExpiry' },
    'send-overdue-notices-daily': { nameKey: 'scheduledTasks.taskNames.overdueNotices' }
  };


  const TIMEZONES = [
    'Africa/Ndjamena',
    'Africa/Douala',
    'Africa/Lagos',
    'Africa/Nairobi',
    'Africa/Cairo',
    'Africa/Casablanca',
    'Africa/Johannesburg',
    'Europe/Paris',
    'Europe/London',
    'America/New_York',
    'America/Chicago',
    'America/Los_Angeles',
    'Asia/Dubai',
    'UTC'
  ];

  // ── Load data ──
  async function loadTasks() {
    loadingTasks = true;
    try {
      tasks = await api.settings.getTasks();
      taskEdits = {};
      for (const t of tasks) {
        taskEdits[t.task_key] = { hour: t.hour, minute: t.minute };
      }
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to load tasks', 'error');
    } finally {
      loadingTasks = false;
    }
  }

  async function loadEmail() {
    loadingEmail = true;
    try {
      email = await api.settings.getEmail();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to load email settings', 'error');
    } finally {
      loadingEmail = false;
    }
  }

  onMount(() => {
    loadTasks();
    loadEmail();
  });

  // ── Task actions ──
  async function toggleTask(task: TaskConfig) {
    togglingTask = task.task_key;
    try {
      const updated = await api.settings.updateTask(task.task_key, {
        is_enabled: !task.is_enabled
      });
      tasks = tasks.map((t) => (t.task_key === updated.task_key ? updated : t));
      showToast(`${get(t)(TASK_LABELS[task.task_key]?.nameKey ?? task.task_key)} ${get(t)(updated.is_enabled ? 'common.enabled' : 'common.disabled')}`);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to update task', 'error');
    } finally {
      togglingTask = null;
    }
  }

  async function saveTaskTime(task: TaskConfig) {
    const edit = taskEdits[task.task_key];
    if (!edit) return;
    savingTask = task.task_key;
    try {
      const updated = await api.settings.updateTask(task.task_key, {
        hour: edit.hour,
        minute: edit.minute
      });
      tasks = tasks.map((t) => (t.task_key === updated.task_key ? updated : t));
      taskEdits[updated.task_key] = { hour: updated.hour, minute: updated.minute };
      showToast($t('scheduledTasks.taskSaved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to update schedule', 'error');
    } finally {
      savingTask = null;
    }
  }

  function taskTimeChanged(task: TaskConfig): boolean {
    const edit = taskEdits[task.task_key];
    if (!edit) return false;
    return edit.hour !== task.hour || edit.minute !== task.minute;
  }

  // ── Email actions ──
  async function saveEmail() {
    savingEmail = true;
    try {
      email = await api.settings.updateEmail(email);
      showToast($t('scheduledTasks.emailSaved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to save email settings', 'error');
    } finally {
      savingEmail = false;
    }
  }

  // Map task keys to notification types (only email-sending tasks)
  const TASK_NOTIFICATION_TYPE: Record<string, string> = {
    'send-rent-reminders-daily': 'rent_reminder',
    'send-lease-expiry-warnings-daily': 'lease_expiry_warning',
    'send-overdue-notices-daily': 'overdue_notice'
  };

  function padTime(n: number): string {
    return String(n).padStart(2, '0');
  }

  // ── SMTP section collapse ──
  let smtpOpen = false;
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
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </a>
      <div>
        <h1 class="text-2xl font-bold text-white">{$t('scheduledTasks.title')}</h1>
        <p class="mt-1 text-sm" style="color: #9dd1f1">{$t('scheduledTasks.subtitle')}</p>
      </div>
    </div>
  </div>

  <!-- Toast -->
  {#if toast}
    <div
      class="fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 transition-all {toast.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}"
    >
      <svg class="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {#if toast.type === 'success'}
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        {:else}
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        {/if}
      </svg>
      <span class="text-sm font-medium">{toast.message}</span>
      <button on:click={() => (toast = null)} class="ml-2 text-current opacity-50 hover:opacity-100">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  {/if}

  <!-- Section: Scheduled Tasks -->
  <section>
    <div class="mb-4 flex items-center gap-2">
      <h2 class="text-lg font-semibold text-gray-900">{$t('scheduledTasks.tasks')}</h2>
      {#if !loadingTasks}
        <span class="ml-auto text-xs text-gray-400">{$t('scheduledTasks.activeCount', { values: { enabled: tasks.filter((t) => t.is_enabled).length, total: tasks.length } })}</span>
      {/if}
    </div>

    {#if loadingTasks}
      <div class="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
        {#each Array(5) as _}
          <div class="animate-pulse border border-gray-200 bg-white p-5">
            <div class="flex items-start justify-between">
              <div class="space-y-2">
                <div class="h-5 w-40 bg-gray-200"></div>
                <div class="h-4 w-64 bg-gray-100"></div>
              </div>
              <div class="h-6 w-11 rounded-full bg-gray-200"></div>
            </div>
            <div class="mt-4 flex items-center gap-3">
              <div class="h-9 w-20 bg-gray-100"></div>
              <div class="h-9 w-20 bg-gray-100"></div>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div class="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
        {#each tasks as task (task.task_key)}
          {@const label = TASK_LABELS[task.task_key]}
          {@const isToggling = togglingTask === task.task_key}
          {@const isSaving = savingTask === task.task_key}
          {@const hasChanges = taskTimeChanged(task)}

          <div
            class="border bg-white transition-all duration-200 {task.is_enabled ? 'border-gray-200 hover:border-gray-300 ' : 'border-gray-100 opacity-60'}"
          >
            <div class="p-5">
              <!-- Card header -->
              <div class="flex items-start justify-between gap-3">
                <div class="flex items-start gap-3">
                  <div>
                    <h3 class="text-sm font-semibold text-gray-900">
                      {$t(label?.nameKey ?? task.task_key)}
                    </h3>
                    <p class="mt-1 text-xs leading-relaxed text-gray-500">
                      {task.description}
                    </p>
                  </div>
                </div>

                <!-- Toggle -->
                <button
                  on:click={() => toggleTask(task)}
                  disabled={isToggling}
                  class="relative mt-0.5 inline-flex h-6 w-11 flex-shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 {task.is_enabled ? 'bg-[#508aa8]' : 'bg-gray-200'} {isToggling ? 'opacity-50' : ''}"
                  aria-label="{task.is_enabled ? $t('common.disabled') : $t('common.enabled')} {$t(label?.nameKey ?? task.task_key)}"
                >
                  <span
                    class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white ring-0 transition-transform duration-200 {task.is_enabled ? 'translate-x-6' : 'translate-x-1'}"
                  ></span>
                </button>
              </div>

              <!-- Schedule controls -->
              <div class="mt-4 flex items-center gap-2 border-t border-gray-100 pt-4">
                <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>

                {#if taskEdits[task.task_key]}
                  <div class="flex items-center gap-1">
                    <input
                      type="number"
                      min="0"
                      max="23"
                      bind:value={taskEdits[task.task_key].hour}
                      disabled={!task.is_enabled}
                      class="w-14 border border-gray-200 bg-gray-50 px-2 py-1.5 text-center text-sm font-mono text-gray-700 focus:border-[#508aa8] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#508aa8] disabled:opacity-50"
                    />
                    <span class="text-gray-400 font-mono">:</span>
                    <input
                      type="number"
                      min="0"
                      max="59"
                      bind:value={taskEdits[task.task_key].minute}
                      disabled={!task.is_enabled}
                      class="w-14 border border-gray-200 bg-gray-50 px-2 py-1.5 text-center text-sm font-mono text-gray-700 focus:border-[#508aa8] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#508aa8] disabled:opacity-50"
                    />
                  </div>

                  {#if hasChanges}
                    <button
                      on:click={() => saveTaskTime(task)}
                      disabled={isSaving}
                      class="ml-1 inline-flex items-center gap-1 bg-[#508aa8] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#3d6f87] focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 disabled:opacity-50 transition-colors"
                    >
                      {#if isSaving}
                        <svg class="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                      {/if}
                      {$t('common.save')}
                    </button>
                  {/if}
                {:else}
                  <span class="text-sm text-gray-500">{padTime(task.hour)}:{padTime(task.minute)}</span>
                {/if}

                <span class="ml-auto text-xs text-gray-400">{task.periodicity}</span>
              </div>

              <!-- Edit Email link (only for email-sending tasks) -->
              {#if TASK_NOTIFICATION_TYPE[task.task_key]}
                <div class="mt-3 border-t border-gray-100 pt-3">
                  <a
                    href="/admin/scheduled-tasks/{TASK_NOTIFICATION_TYPE[task.task_key]}"
                    class="inline-flex items-center gap-1.5 text-xs font-medium text-[#508aa8] hover:text-[#031927] transition-colors"
                  >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    {$t('scheduledTasks.notificationTemplates')}
                  </a>
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </section>

  <!-- Section: Email & SMTP Settings -->
  <section>
    <button
      type="button"
      on:click={() => (smtpOpen = !smtpOpen)}
      class="mb-4 flex w-full items-center gap-2 border border-gray-200 bg-white px-5 py-4 hover:bg-gray-50 transition-colors text-left"
    >
      <div class="flex-1 min-w-0">
        <h2 class="text-sm font-semibold text-gray-900">{$t('scheduledTasks.emailSettings')}</h2>
        <p class="text-xs text-gray-500 mt-0.5">{$t('scheduledTasks.emailSettingsDescription')}</p>
      </div>
      <svg
        class="h-5 w-5 flex-shrink-0 text-gray-400 transition-transform duration-200 {smtpOpen ? 'rotate-180' : ''}"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    {#if smtpOpen}
    {#if loadingEmail}
      <div class="animate-pulse border border-gray-200 bg-white p-6">
        <div class="grid gap-4 sm:grid-cols-2">
          {#each Array(6) as _}
            <div class="space-y-2">
              <div class="h-4 w-24 bg-gray-200"></div>
              <div class="h-10 w-full bg-gray-100"></div>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <form on:submit|preventDefault={saveEmail} class="border border-gray-200 bg-white">
        <div class="p-6">
          <div class="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <!-- SMTP Host -->
            <div>
              <label for="smtp_host" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.smtpHost')}</label>
              <input
                id="smtp_host"
                type="text"
                bind:value={email.smtp_host}
                placeholder="smtp.gmail.com"
                class="input mt-1"
              />
            </div>

            <!-- SMTP Port -->
            <div>
              <label for="smtp_port" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.smtpPort')}</label>
              <input
                id="smtp_port"
                type="number"
                min="1"
                max="65535"
                bind:value={email.smtp_port}
                class="input mt-1"
              />
            </div>

            <!-- SMTP Username -->
            <div>
              <label for="smtp_username" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.smtpUsername')}</label>
              <input
                id="smtp_username"
                type="text"
                bind:value={email.smtp_username}
                placeholder="user@example.com"
                class="input mt-1"
              />
            </div>

            <!-- SMTP Password -->
            <div>
              <label for="smtp_password" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.smtpPassword')}</label>
              <input
                id="smtp_password"
                type="password"
                bind:value={email.smtp_password}
                placeholder="Enter password"
                class="input mt-1"
              />
            </div>

            <!-- Sender Name -->
            <div>
              <label for="from_name" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.fromName')}</label>
              <input
                id="from_name"
                type="text"
                bind:value={email.from_name}
                placeholder="Immobilière ABC"
                class="input mt-1"
              />
            </div>

            <!-- From Email -->
            <div>
              <label for="from_email" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.fromEmail')}</label>
              <input
                id="from_email"
                type="email"
                bind:value={email.from_email}
                placeholder="noreply@yourdomain.com"
                class="input mt-1"
              />
            </div>

            <!-- Reply-To Email -->
            <div>
              <label for="reply_to_email" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.replyTo')}</label>
              <input
                id="reply_to_email"
                type="email"
                bind:value={email.reply_to_email}
                placeholder="contact@yourdomain.com"
                class="input mt-1"
              />
            </div>

            <!-- Timezone -->
            <div>
              <label for="task_timezone" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.timezone')}</label>
              <select
                id="task_timezone"
                bind:value={email.task_timezone}
                class="input mt-1"
              >
                {#each TIMEZONES as tz}
                  <option value={tz}>{tz}</option>
                {/each}
              </select>
            </div>

            <!-- TLS Toggle — full width -->
            <div class="sm:col-span-2">
              <div class="flex items-center gap-3">
                <button
                  type="button"
                  on:click={() => (email.smtp_use_tls = !email.smtp_use_tls)}
                  class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 {email.smtp_use_tls ? 'bg-[#508aa8]' : 'bg-gray-200'}"
                  aria-label="Toggle TLS"
                >
                  <span
                    class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white ring-0 transition-transform duration-200 {email.smtp_use_tls ? 'translate-x-6' : 'translate-x-1'}"
                  ></span>
                </button>
                <div>
                  <span class="text-sm font-medium text-gray-700">{$t('scheduledTasks.smtpTls')}</span>
                  <span class="ml-1 text-xs text-gray-400">{$t('scheduledTasks.tlsNote')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50 px-6 py-4 -xl">
          <button
            type="button"
            on:click={loadEmail}
            class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {$t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={savingEmail}
            class="inline-flex items-center gap-2 bg-[#508aa8] px-4 py-2 text-sm font-medium text-white hover:bg-[#3d6f87] focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 disabled:opacity-50 transition-colors"
          >
            {#if savingEmail}
              <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
            {/if}
            {savingEmail ? $t('common.saving') : $t('common.saveChanges')}
          </button>
        </div>
      </form>
    {/if}
    {/if}
  </section>
</div>

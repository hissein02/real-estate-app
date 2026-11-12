<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { t } from 'svelte-i18n';
  import { get } from 'svelte/store';
  import { api } from '$lib/api/client';
  import type { NotificationTemplateData } from '$lib/api/types';
  import RichTextEditor from '$lib/components/RichTextEditor.svelte';

  const notificationType: string = $page.params.type ?? '';

  // ── State ──
  let template: NotificationTemplateData | null = null;
  let loading = true;
  let saving = false;
  let sendingTest = false;
  let testEmail = '';

  // Editable copies
  let editSubject = '';
  let editBody = '';

  // Key to force-remount the RichTextEditor when resetting
  let editorKey = 0;

  // Toast
  let toast: { message: string; type: 'success' | 'error' } | null = null;
  let toastTimeout: ReturnType<typeof setTimeout>;

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast = { message, type };
    toastTimeout = setTimeout(() => (toast = null), 5000);
  }

  // ── Human-readable labels ──
  function getTypeName(type: string): string {
    const T = get(t);
    const key = `notifications.types.${type}`;
    const translated = T(key);
    return translated !== key ? translated : type;
  }

  const VARIABLE_DESCRIPTIONS: Record<string, Record<string, string>> = {
    rent_reminder: {
      tenant_name: "Tenant's full name",
      invoice_number: 'Invoice reference number (e.g. INV-2026-001)',
      total_amount: 'Total amount due, formatted (e.g. 150 000)',
      currency: 'Currency label (e.g. FCFA)',
      due_date: 'Payment due date (DD-MM-YYYY)'
    },
    overdue_notice: {
      tenant_name: "Tenant's full name",
      invoice_number: 'Invoice reference number',
      balance: 'Outstanding balance, formatted',
      currency: 'Currency label',
      due_date: 'Original due date (DD-MM-YYYY)',
      days_overdue: 'Number of days past due'
    },
    lease_expiry_warning: {
      tenant_name: "Tenant's full name",
      unit: 'Unit name and property',
      end_date: 'Lease end date (DD-MM-YYYY)'
    }
  };

  // ── Load ──
  async function loadTemplate() {
    loading = true;
    try {
      template = await api.settings.getTemplate(notificationType);
      editSubject = template.subject_template;
      editBody = template.body_template;
      editorKey += 1;
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to load template', 'error');
    } finally {
      loading = false;
    }
  }

  onMount(loadTemplate);

  // ── Save ──
  async function saveTemplate() {
    saving = true;
    try {
      template = await api.settings.updateTemplate(notificationType, {
        subject_template: editSubject,
        body_template: editBody
      });
      editSubject = template.subject_template;
      editBody = template.body_template;
      showToast(get(t)('scheduledTasks.template.saved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to save template', 'error');
    } finally {
      saving = false;
    }
  }

  // ── Reset ──
  function resetTemplate() {
    if (template) {
      editSubject = template.subject_template;
      editBody = template.body_template;
      editorKey += 1;
    }
  }

  // ── Send test ──
  async function sendTest() {
    if (!testEmail) {
      showToast(get(t)('scheduledTasks.template.emailRequired'), 'error');
      return;
    }
    sendingTest = true;
    try {
      const res = await api.settings.sendTestEmail(notificationType, testEmail);
      showToast(res.detail || 'Test email sent!');
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to send test email', 'error');
    } finally {
      sendingTest = false;
    }
  }

  // ── Rich text change handler ──
  function handleBodyChange(e: CustomEvent<string>) {
    editBody = e.detail;
  }

  // ── Preview rendering ──
  function renderPreview(tpl: string, sampleData: Record<string, string>): string {
    let result = tpl;
    for (const [key, value] of Object.entries(sampleData)) {
      result = result.replaceAll(`{${key}}`, value);
    }
    return result;
  }

  $: hasChanges =
    template !== null &&
    (editSubject !== template.subject_template || editBody !== template.body_template);

  $: previewSubject = template ? renderPreview(editSubject, template.sample_data) : '';
  $: previewBody = template ? renderPreview(editBody, template.sample_data) : '';
</script>

<div class="space-y-8">
  <!-- Header -->
  <div class="flex items-center gap-4">
    <a
      href="/admin/scheduled-tasks"
      aria-label={$t('common.back')}
      class="inline-flex items-center justify-center border border-gray-300 bg-white p-2 text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
    >
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
      </svg>
    </a>
    <div>
      <h1 class="text-2xl font-bold text-gray-900">
        {getTypeName(notificationType)} — {$t('scheduledTasks.template.editorTitle')}
      </h1>
      <p class="mt-1 text-sm text-gray-500">
        {$t('scheduledTasks.template.subtitle')}
      </p>
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

  {#if loading}
    <div class="space-y-6">
      <div class="animate-pulse border border-gray-200 bg-white p-6">
        <div class="space-y-4">
          <div class="h-4 w-32 bg-gray-200"></div>
          <div class="h-10 w-full bg-gray-100"></div>
          <div class="h-4 w-32 bg-gray-200"></div>
          <div class="h-40 w-full bg-gray-100"></div>
        </div>
      </div>
    </div>
  {:else if template}
    <div class="grid gap-6 lg:grid-cols-3">
      <!-- Left: Editor (2/3) -->
      <div class="lg:col-span-2 space-y-6">
        <!-- Template Editor -->
        <form on:submit|preventDefault={saveTemplate} class="border border-gray-200 bg-white">
          <div class="border-b border-gray-100 px-6 py-4">
            <h2 class="text-sm font-semibold text-gray-900">{$t('scheduledTasks.template.editorTitle')}</h2>
            <p class="mt-0.5 text-xs text-gray-500">
              {$t('scheduledTasks.template.editorHint')}
            </p>
          </div>

          <div class="space-y-5 p-6">
            <!-- Subject -->
            <div>
              <label for="subject" class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.template.subjectLine')}</label>
              <input
                id="subject"
                type="text"
                bind:value={editSubject}
                class="input mt-1 font-mono"
              />
            </div>

            <!-- Body (Rich Text) -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">{$t('scheduledTasks.template.emailBody')}</label>
              {#key editorKey}
                <RichTextEditor content={editBody} on:change={handleBodyChange} />
              {/key}
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between gap-3 border-t border-gray-100 bg-gray-50 px-6 py-4 -xl">
            <button
              type="button"
              on:click={resetTemplate}
              class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {$t('scheduledTasks.template.reset')}
            </button>
            <button
              type="submit"
              disabled={saving || !hasChanges}
              class="btn-primary"
            >
              {#if saving}
                <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              {/if}
              {saving ? $t('common.saving') : $t('scheduledTasks.template.save')}
            </button>
          </div>
        </form>

        <!-- Preview -->
        <div class="border border-gray-200 bg-white">
          <div class="border-b border-gray-100 px-6 py-4">
            <h2 class="text-sm font-semibold text-gray-900">{$t('scheduledTasks.template.livePreview')}</h2>
            <p class="mt-0.5 text-xs text-gray-500">{$t('scheduledTasks.template.previewHint')}</p>
          </div>
          <div class="p-6">
            <div class="border border-gray-200 bg-gray-50 overflow-hidden">
              <!-- Email header -->
              <div class="border-b border-gray-200 bg-white px-4 py-3">
                <div class="flex items-center gap-2 text-xs text-gray-500">
                  <span class="font-medium text-gray-700">{$t('scheduledTasks.template.subjectLabel')}</span>
                  <span class="text-gray-900">{previewSubject}</span>
                </div>
              </div>
              <!-- Email body -->
              <div class="email-preview px-4 py-4 text-sm text-gray-800 leading-relaxed">
                {@html previewBody}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Sidebar (1/3) -->
      <div class="space-y-6">
        <!-- Available Variables -->
        <div class="border border-gray-200 bg-white">
          <div class="border-b border-gray-100 px-5 py-4">
            <h2 class="text-sm font-semibold text-gray-900">{$t('scheduledTasks.template.availableVariables')}</h2>
            <p class="mt-0.5 text-xs text-gray-500">{$t('scheduledTasks.template.variablesHint')}</p>
          </div>
          <div class="p-4">
            <div class="space-y-2">
              {#each template.available_variables as variable}
                {@const description = VARIABLE_DESCRIPTIONS[notificationType]?.[variable] ?? ''}
                <button
                  type="button"
                  on:click={() => navigator.clipboard.writeText(`{${variable}}`)}
                  class="flex w-full items-start gap-2 border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:bg-gray-100 transition-colors group"
                >
                  <code class="flex-shrink-0 bg-white px-1.5 py-0.5 text-xs font-mono text-gray-800 border border-gray-200">
                    {`{${variable}}`}
                  </code>
                  {#if description}
                    <span class="text-xs text-gray-500 leading-relaxed">{description}</span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        </div>

        <!-- Send Test Email -->
        <div class="border border-gray-200 bg-white">
          <div class="border-b border-gray-100 px-5 py-4">
            <h2 class="text-sm font-semibold text-gray-900">{$t('scheduledTasks.template.sendTestTitle')}</h2>
            <p class="mt-0.5 text-xs text-gray-500">
              {$t('scheduledTasks.template.sendTestHint')}
            </p>
          </div>
          <div class="p-4 space-y-3">
            <div>
              <label for="test-email" class="block text-xs font-medium text-gray-700">{$t('scheduledTasks.template.recipient')}</label>
              <input
                id="test-email"
                type="email"
                bind:value={testEmail}
                placeholder="you@example.com"
                class="input mt-1"
              />
            </div>
            <button
              on:click={sendTest}
              disabled={sendingTest || !testEmail}
              class="btn-primary w-full"
            >
              {#if sendingTest}
                <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                {$t('common.sending')}
              {:else}
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                {$t('scheduledTasks.template.sendTest')}
              {/if}
            </button>
            <p class="text-xs text-gray-400 text-center">
              {$t('scheduledTasks.template.testNote')}
            </p>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .email-preview :global(p) {
    margin: 0.25em 0;
  }
  .email-preview :global(strong) {
    font-weight: 700;
  }
  .email-preview :global(em) {
    font-style: italic;
  }
  .email-preview :global(u) {
    text-decoration: underline;
  }
  .email-preview :global(ul) {
    list-style-type: disc;
    padding-left: 1.5em;
    margin: 0.25em 0;
  }
  .email-preview :global(ol) {
    list-style-type: decimal;
    padding-left: 1.5em;
    margin: 0.25em 0;
  }
</style>

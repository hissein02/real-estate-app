<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { t } from 'svelte-i18n';
  import { api, mediaUrl } from '$lib/api/client';
  import { companyInfo, setCompanyInfo } from '$lib/stores/auth';
  import type { CompanyInfoData, Signatory } from '$lib/api/types';
  import RichTextEditor from '$lib/components/RichTextEditor.svelte';

  let loading = true;

  // ── Display preferences state ──
  let pdfShowRccm = true;
  let pdfShowNif = true;
  let pdfBankDisplay: 'none' | 'all' | 'selected' = 'all';
  let pdfSelectedBankIndices: number[] = [];
  let savingPrefs = false;

  // Signatory state
  let signatories: Signatory[] = [];
  let selectedSignatoryId: number | null = null;

  // Company details needed for display
  let rccm = '';
  let nif = '';
  let bankAccounts: { bank_name: string; account_number: string }[] = [];

  // ── Email template state ──
  let templateExpanded = false;
  let subjectTemplate = '';
  let bodyTemplate = '';
  let originalSubject = '';
  let originalBody = '';
  let templateVariables: string[] = [];
  let sampleData: Record<string, string> = {};
  let savingTemplate = false;
  let loadingTemplate = false;

  // ── Email preview ──
  let previewHtml = '';
  let loadingPreview = false;

  // ── Test email ──
  let testEmail = '';
  let sendingTest = false;

  // ── Toast ──
  let toast: { message: string; type: 'success' | 'error' } | null = null;
  let toastTimeout: ReturnType<typeof setTimeout>;

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast = { message, type };
    toastTimeout = setTimeout(() => (toast = null), 4000);
  }

  function populateFromCompany(data: CompanyInfoData) {
    pdfShowRccm = data.pdf_show_rccm ?? true;
    pdfShowNif = data.pdf_show_nif ?? true;
    pdfBankDisplay = data.pdf_bank_display ?? 'all';
    pdfSelectedBankIndices = data.pdf_selected_bank_indices ?? [];
    selectedSignatoryId = data.pdf_signatory?.id ?? null;
    rccm = data.rccm || '';
    nif = data.nif || '';
    bankAccounts = data.bank_accounts ?? [];
  }

  function toggleBankIndex(index: number) {
    if (pdfSelectedBankIndices.includes(index)) {
      pdfSelectedBankIndices = pdfSelectedBankIndices.filter(i => i !== index);
    } else {
      pdfSelectedBankIndices = [...pdfSelectedBankIndices, index];
    }
  }

  // Computed
  $: validBanks = bankAccounts
    .map((b, i) => ({ ...b, originalIndex: i }))
    .filter(b => b.bank_name.trim() || b.account_number.trim());

  onMount(async () => {
    try {
      const [data, sigs] = await Promise.all([
        api.settings.getCompany(),
        api.signatories.list(),
      ]);
      setCompanyInfo(data);
      populateFromCompany(data);
      signatories = sigs;
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.errorLoading'), 'error');
    } finally {
      loading = false;
    }
  });

  function handleResetPrefs() {
    if ($companyInfo) populateFromCompany($companyInfo);
  }

  async function handleSavePrefs() {
    savingPrefs = true;
    try {
      const data = await api.settings.updateCompany({
        pdf_show_rccm: pdfShowRccm,
        pdf_show_nif: pdfShowNif,
        pdf_bank_display: pdfBankDisplay,
        pdf_selected_bank_indices: pdfSelectedBankIndices,
        pdf_signatory_id: selectedSignatoryId
      });
      setCompanyInfo(data);
      showToast($t('invoiceSettings.saved'));
      // Refresh preview after saving preferences
      if (templateExpanded) loadPreview();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to save', 'error');
    } finally {
      savingPrefs = false;
    }
  }

  // ── Email Template ──
  async function openTemplate() {
    templateExpanded = true;
    loadingTemplate = true;
    try {
      const [tpl] = await Promise.all([
        api.settings.getTemplate('invoice_generated'),
        loadPreview()
      ]);
      subjectTemplate = tpl.subject_template;
      bodyTemplate = tpl.body_template || '';
      originalSubject = tpl.subject_template;
      originalBody = tpl.body_template || '';
      templateVariables = tpl.available_variables;
      sampleData = tpl.sample_data;
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to load template', 'error');
    } finally {
      loadingTemplate = false;
    }
  }

  async function loadPreview() {
    loadingPreview = true;
    try {
      const res = await api.settings.getInvoiceEmailPreview();
      previewHtml = res.html;
    } catch {
      previewHtml = '<p style="padding:20px;color:#666;">Failed to load preview</p>';
    } finally {
      loadingPreview = false;
    }
  }

  async function handleSaveTemplate() {
    savingTemplate = true;
    try {
      const tpl = await api.settings.updateTemplate('invoice_generated', {
        subject_template: subjectTemplate,
        body_template: bodyTemplate
      });
      originalSubject = tpl.subject_template;
      originalBody = tpl.body_template || '';
      showToast($t('invoiceSettings.templateSaved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to save', 'error');
    } finally {
      savingTemplate = false;
    }
  }

  function insertVariableInSubject(varName: string) {
    subjectTemplate += `{${varName}}`;
  }

  async function handleSendTest() {
    if (!testEmail.trim()) return;
    sendingTest = true;
    try {
      await api.settings.sendTestInvoiceEmail(testEmail.trim());
      showToast($t('invoiceSettings.testSent'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Failed to send test email', 'error');
    } finally {
      sendingTest = false;
    }
  }

  // Variable descriptions
  const variableDescriptions: Record<string, string> = {
    tenant_name: 'Tenant full name',
    invoice_number: 'Invoice reference number',
    total_amount: 'Total invoice amount',
    currency: 'Currency label (e.g. FCFA)',
    due_date: 'Payment due date',
    company_name: 'Your company name',
  };
</script>

<!-- Toast -->
{#if toast}
  <div class="fixed right-4 top-4 z-50 animate-in fade-in slide-in-from-top-2">
    <div
      class="flex items-center gap-2 px-4 py-3 text-sm font-medium {toast.type === 'success' ? 'bg-green-50 text-green-800 ring-1 ring-green-200' : 'bg-red-50 text-red-800 ring-1 ring-red-200'}"
    >
      {toast.message}
    </div>
  </div>
{/if}

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
        <h1 class="text-2xl font-bold text-white">{$t('invoiceSettings.title')}</h1>
        <p class="mt-1 text-sm" style="color: #9dd1f1">{$t('invoiceSettings.subtitle')}</p>
      </div>
    </div>
  </div>

  {#if loading}
    <div class="flex justify-center py-20">
      <svg class="h-8 w-8 animate-spin text-primary-600" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  {:else}

    <!-- ═══════════════════════════════════════════════ -->
    <!-- Card 1: Invoice Display Preferences            -->
    <!-- ═══════════════════════════════════════════════ -->
    <div class="border border-gray-200 bg-white">
      <div class="border-b border-gray-100 px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center bg-[#508aa8]/10">
            <svg class="h-5 w-5 text-[#508aa8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h2 class="text-base font-semibold text-gray-900">{$t('invoiceSettings.displayPreferences')}</h2>
            <p class="text-xs text-gray-500">{$t('invoiceSettings.displayPreferencesDescription')}</p>
          </div>
        </div>
      </div>

      <div class="divide-y divide-gray-100">
        <!-- Legal References -->
        <div class="px-6 py-5">
          <h3 class="text-sm font-medium text-gray-700">{$t('invoiceSettings.legalReferences')}</h3>
          <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.legalReferencesHint')}</p>
          <div class="mt-4 space-y-3">
            <label class="flex items-center justify-between border border-gray-200 px-4 py-3 transition-colors hover:bg-gray-50">
              <div class="flex items-center gap-3">
                <div class="flex-1">
                  <span class="text-sm font-medium text-gray-700">{$t('invoiceSettings.showRccm')}</span>
                  {#if rccm.trim()}
                    <span class="ml-2 text-xs text-gray-400">{rccm}</span>
                  {:else}
                    <span class="ml-2 text-xs italic text-gray-300">{$t('invoiceSettings.notSet')}</span>
                  {/if}
                </div>
              </div>
              <div class="relative">
                <input type="checkbox" bind:checked={pdfShowRccm} class="peer sr-only" />
                <div class="h-6 w-11 rounded-full bg-gray-200 transition-colors after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after: after:transition-transform peer-checked:bg-primary-600 peer-checked:after:translate-x-5 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2"></div>
              </div>
            </label>
            <label class="flex items-center justify-between border border-gray-200 px-4 py-3 transition-colors hover:bg-gray-50">
              <div class="flex items-center gap-3">
                <div class="flex-1">
                  <span class="text-sm font-medium text-gray-700">{$t('invoiceSettings.showNif')}</span>
                  {#if nif.trim()}
                    <span class="ml-2 text-xs text-gray-400">{nif}</span>
                  {:else}
                    <span class="ml-2 text-xs italic text-gray-300">{$t('invoiceSettings.notSet')}</span>
                  {/if}
                </div>
              </div>
              <div class="relative">
                <input type="checkbox" bind:checked={pdfShowNif} class="peer sr-only" />
                <div class="h-6 w-11 rounded-full bg-gray-200 transition-colors after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after: after:transition-transform peer-checked:bg-primary-600 peer-checked:after:translate-x-5 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2"></div>
              </div>
            </label>
          </div>
        </div>

        <!-- Bank Details -->
        <div class="px-6 py-5">
          <h3 class="text-sm font-medium text-gray-700">{$t('invoiceSettings.bankDisplay')}</h3>
          <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.bankDisplayHint')}</p>
          <div class="mt-4 inline-flex border border-gray-200 bg-gray-50 p-1">
            <button type="button" on:click={() => (pdfBankDisplay = 'none')}
              class="px-3.5 py-1.5 text-xs font-medium transition-all {pdfBankDisplay === 'none' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
              {$t('invoiceSettings.bankDisplayNone')}
            </button>
            <button type="button" on:click={() => (pdfBankDisplay = 'all')}
              class="px-3.5 py-1.5 text-xs font-medium transition-all {pdfBankDisplay === 'all' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
              {$t('invoiceSettings.bankDisplayAll')}
            </button>
            <button type="button" on:click={() => (pdfBankDisplay = 'selected')}
              class="px-3.5 py-1.5 text-xs font-medium transition-all {pdfBankDisplay === 'selected' ? 'bg-white text-gray-900 ' : 'text-gray-500 hover:text-gray-700'}">
              {$t('invoiceSettings.bankDisplaySelected')}
            </button>
          </div>

          {#if pdfBankDisplay === 'selected'}
            <div class="mt-3 space-y-2">
              {#if validBanks.length === 0}
                <p class="border border-dashed border-gray-200 px-4 py-3 text-center text-xs text-gray-400">
                  {$t('invoiceSettings.noBankAccounts')}
                </p>
              {:else}
                {#each validBanks as bank}
                  <label class="flex cursor-pointer items-center gap-3 border border-gray-200 px-4 py-2.5 transition-colors hover:bg-gray-50 {pdfSelectedBankIndices.includes(bank.originalIndex) ? 'border-primary-200 bg-primary-50/50' : ''}">
                    <input
                      type="checkbox"
                      checked={pdfSelectedBankIndices.includes(bank.originalIndex)}
                      on:change={() => toggleBankIndex(bank.originalIndex)}
                      class="h-4 w-4 border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <div class="flex-1 text-sm">
                      <span class="font-medium text-gray-700">{bank.bank_name || $t('invoiceSettings.unnamed')}</span>
                      <span class="ml-1.5 text-gray-400">—</span>
                      <span class="ml-1.5 text-gray-500">{bank.account_number || '...'}</span>
                    </div>
                  </label>
                {/each}
              {/if}
            </div>
          {/if}
        </div>

        <!-- Signatory -->
        <div class="px-6 py-5">
          <h3 class="text-sm font-medium text-gray-700">{$t('invoiceSettings.signatory')}</h3>
          <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.signatoryHint')}</p>

          <div class="mt-4 space-y-2">
            <!-- None option -->
            <label class="flex cursor-pointer items-center gap-3 border border-gray-200 px-4 py-3 transition-colors hover:bg-gray-50 {selectedSignatoryId === null ? 'border-primary-200 bg-primary-50/50' : ''}">
              <input
                type="radio"
                bind:group={selectedSignatoryId}
                value={null}
                class="h-4 w-4 border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span class="text-sm font-medium text-gray-700">{$t('invoiceSettings.signatoryNone')}</span>
            </label>

            {#each signatories as sig (sig.id)}
              <label class="flex cursor-pointer items-center gap-3 border border-gray-200 px-4 py-3 transition-colors hover:bg-gray-50 {selectedSignatoryId === sig.id ? 'border-primary-200 bg-primary-50/50' : ''}">
                <input
                  type="radio"
                  bind:group={selectedSignatoryId}
                  value={sig.id}
                  class="h-4 w-4 border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <div class="flex flex-1 items-center gap-3">
                  <div class="flex-1">
                    <span class="text-sm font-semibold text-gray-800">{sig.label}</span>
                    {#if sig.name}
                      <span class="ml-1.5 text-sm text-gray-500">— {sig.name}</span>
                    {/if}
                  </div>
                  {#if sig.signature_url}
                    <img
                      src={mediaUrl(sig.signature_url)}
                      alt="Signature"
                      class="h-8 max-w-[80px] object-contain border border-gray-100 bg-white p-0.5"
                    />
                  {/if}
                </div>
              </label>
            {/each}

            {#if signatories.length === 0}
              <p class="border border-dashed border-gray-200 px-4 py-4 text-center text-sm text-gray-400">
                {$t('invoiceSettings.noSignatoryConfigured')}
                <a href="/admin/company" class="ml-1 text-primary-600 hover:underline">{$t('invoiceSettings.signatoryLink')}</a>
              </p>
            {/if}
          </div>
        </div>
      </div>

      <!-- Save / Reset -->
      <div class="flex items-center justify-end gap-3 border-t border-gray-100 px-6 py-4">
        <button type="button" on:click={handleResetPrefs}
          class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50">
          {$t('common.reset')}
        </button>
        <button type="button" on:click={handleSavePrefs} disabled={savingPrefs}
          class="inline-flex items-center gap-2 bg-primary-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50">
          {#if savingPrefs}
            <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          {/if}
          {savingPrefs ? $t('common.saving') : $t('common.saveChanges')}
        </button>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════════ -->
    <!-- Card 2: Email Templates                        -->
    <!-- ═══════════════════════════════════════════════ -->
    <div class="border border-gray-200 bg-white">
      <div class="border-b border-gray-100 px-6 py-4">
        <h2 class="text-base font-semibold text-gray-900">{$t('invoiceSettings.emailTemplates')}</h2>
        <p class="text-xs text-gray-500">{$t('invoiceSettings.invoiceEmailDescription')}</p>
      </div>

      <div class="p-6">
        <!-- Template card: Invoice Email -->
        <button
          type="button"
          on:click={() => templateExpanded ? (templateExpanded = false) : openTemplate()}
          class="group flex w-full items-center gap-4 border border-gray-200 p-4 text-left transition-colors hover:bg-gray-50 {templateExpanded ? 'bg-gray-50' : ''}"
        >
          <div class="flex-1 min-w-0">
            <h3 class="text-sm font-semibold text-gray-900">{$t('invoiceSettings.invoiceEmail')}</h3>
            <p class="mt-0.5 text-xs text-gray-500">{$t('invoiceSettings.invoiceEmailDescription')}</p>
          </div>
          <svg
            class="h-5 w-5 flex-shrink-0 text-gray-400 transition-transform {templateExpanded ? 'rotate-180' : ''}"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Expanded template editor -->
        {#if templateExpanded}
          <div class="mt-6">
            {#if loadingTemplate}
              <div class="flex justify-center py-12">
                <svg class="h-6 w-6 animate-spin text-primary-600" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            {:else}
              <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <!-- Left: Subject + Body + Variables + Test Email -->
                <div class="space-y-5 lg:col-span-1">
                  <!-- Subject -->
                  <div>
                    <label for="subjectTemplate" class="block text-sm font-medium text-gray-700">{$t('invoiceSettings.subjectLine')}</label>
                    <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.subjectHint')}</p>
                    <input
                      id="subjectTemplate"
                      type="text"
                      bind:value={subjectTemplate}
                      class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                    />
                  </div>

                  <!-- Body -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700">{$t('scheduledTasks.body')}</label>
                    <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.bodyHint')}</p>
                    <div class="mt-2">
                      <RichTextEditor
                        content={bodyTemplate}
                        on:change={(e) => (bodyTemplate = e.detail)}
                      />
                    </div>
                  </div>

                  <!-- Available Variables -->
                  <div>
                    <h4 class="text-xs font-semibold uppercase tracking-wider text-gray-400">{$t('invoiceSettings.variables')}</h4>
                    <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.variablesHint')}</p>
                    <div class="mt-2 space-y-1.5">
                      {#each templateVariables as varName}
                        <button
                          type="button"
                          on:click={() => insertVariableInSubject(varName)}
                          class="group flex w-full items-center gap-2 border border-gray-200 px-3 py-2 text-left text-xs transition-colors hover:border-primary-200 hover:bg-primary-50"
                        >
                          <code class="bg-gray-100 px-1.5 py-0.5 font-mono text-primary-600 group-hover:bg-primary-100">{`{${varName}}`}</code>
                          <span class="flex-1 text-gray-500">{variableDescriptions[varName] || varName}</span>
                        </button>
                      {/each}
                    </div>
                  </div>

                  <!-- Save template -->
                  <div class="flex items-center gap-3">
                    <button type="button" on:click={() => { subjectTemplate = originalSubject; bodyTemplate = originalBody; }}
                      class="border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50">
                      {$t('invoiceSettings.resetTemplate')}
                    </button>
                    <button type="button" on:click={handleSaveTemplate} disabled={savingTemplate}
                      class="inline-flex items-center gap-1.5 bg-primary-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50">
                      {#if savingTemplate}
                        <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      {/if}
                      {savingTemplate ? $t('common.saving') : $t('invoiceSettings.saveTemplate')}
                    </button>
                  </div>

                  <!-- Test Email -->
                  <div class="border border-gray-200 p-4">
                    <h4 class="text-sm font-medium text-gray-700">{$t('invoiceSettings.sendTestEmail')}</h4>
                    <p class="mt-0.5 text-xs text-gray-400">{$t('invoiceSettings.sendTestDescription')}</p>
                    <div class="mt-3 flex gap-2">
                      <input
                        type="email"
                        bind:value={testEmail}
                        placeholder={$t('invoiceSettings.recipient')}
                        class="block flex-1 border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                      />
                      <button
                        type="button"
                        on:click={handleSendTest}
                        disabled={sendingTest || !testEmail.trim()}
                        class="inline-flex items-center gap-1.5 bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-50"
                      >
                        {#if sendingTest}
                          <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        {:else}
                          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                          </svg>
                        {/if}
                        {sendingTest ? $t('common.sending') : $t('common.send')}
                      </button>
                    </div>
                    <p class="mt-2 text-[10px] text-gray-400">{$t('invoiceSettings.testSubjectNote')}</p>
                  </div>
                </div>

                <!-- Right: Email Preview -->
                <div class="lg:col-span-2">
                  <div class="border border-gray-200 overflow-hidden">
                    <div class="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2.5">
                      <span class="text-xs font-medium text-gray-500">{$t('invoiceSettings.emailPreview')}</span>
                      <button
                        type="button"
                        on:click={loadPreview}
                        disabled={loadingPreview}
                        class="inline-flex items-center gap-1 text-xs text-gray-400 transition-colors hover:text-gray-600"
                      >
                        <svg class="h-3.5 w-3.5 {loadingPreview ? 'animate-spin' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {$t('invoiceSettings.previewRefresh')}
                      </button>
                    </div>
                    {#if loadingPreview}
                      <div class="flex justify-center bg-gray-100 py-32">
                        <svg class="h-6 w-6 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      </div>
                    {:else}
                      <iframe
                        title="Invoice Email Preview"
                        srcdoc={previewHtml}
                        class="w-full bg-gray-100"
                        style="height: 700px; border: none;"
                        sandbox="allow-same-origin"
                      />
                    {/if}
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>

  {/if}
</div>

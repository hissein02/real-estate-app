<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { t } from 'svelte-i18n';
  import { api, mediaUrl } from '$lib/api/client';
  import { companyInfo, setCompanyInfo } from '$lib/stores/auth';
  import type { CompanyInfoData, BankAccount, Signatory } from '$lib/api/types';
  import LogoUpload from '$lib/components/LogoUpload.svelte';

  let loading = true;
  let saving = false;
  let uploadingLogo = false;

  // Form state — Company details
  let displayName = '';
  let companyName = '';
  let address = '';
  let city = '';
  let country = '';
  let phoneNumbers: string[] = [''];
  let email = '';
  let logoUrl: string | null = null;
  let bankAccounts: BankAccount[] = [{ bank_name: '', account_number: '' }];
  let rccm = '';
  let nif = '';

  // Signatories
  let signatories: Signatory[] = [];
  let loadingSignatories = false;

  // New signatory form
  let newLabel = '';
  let newName = '';
  let newSignatureFile: File | null = null;
  let addingSignatory = false;
  let showAddForm = false;

  // Per-signatory upload state
  let uploadingSignatureFor: number | null = null;
  let savingSignatoryId: number | null = null;

  // Toast
  let toast: { message: string; type: 'success' | 'error' } | null = null;
  let toastTimeout: ReturnType<typeof setTimeout>;

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast = { message, type };
    toastTimeout = setTimeout(() => (toast = null), 4000);
  }

  function populateForm(data: CompanyInfoData) {
    displayName = data.display_name || '';
    companyName = data.company_name || '';
    address = data.address || '';
    city = data.city || '';
    country = data.country || '';
    phoneNumbers = data.phone_numbers?.length ? [...data.phone_numbers] : [''];
    email = data.email || '';
    logoUrl = data.logo_url;
    bankAccounts = data.bank_accounts?.length
      ? data.bank_accounts.map(b => ({ ...b }))
      : [{ bank_name: '', account_number: '' }];
    rccm = data.rccm || '';
    nif = data.nif || '';
  }

  async function loadSignatories() {
    loadingSignatories = true;
    try {
      signatories = await api.signatories.list();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.errorLoading'), 'error');
    } finally {
      loadingSignatories = false;
    }
  }

  onMount(async () => {
    try {
      const data = await api.settings.getCompany();
      setCompanyInfo(data);
      populateForm(data);
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.errorLoading'), 'error');
    } finally {
      loading = false;
    }
    loadSignatories();
  });

  function addPhone() {
    phoneNumbers = [...phoneNumbers, ''];
  }

  function removePhone(index: number) {
    phoneNumbers = phoneNumbers.filter((_, i) => i !== index);
    if (phoneNumbers.length === 0) phoneNumbers = [''];
  }

  function addBank() {
    bankAccounts = [...bankAccounts, { bank_name: '', account_number: '' }];
  }

  function removeBank(index: number) {
    bankAccounts = bankAccounts.filter((_, i) => i !== index);
    if (bankAccounts.length === 0) bankAccounts = [{ bank_name: '', account_number: '' }];
  }

  function handleReset() {
    if ($companyInfo) {
      populateForm($companyInfo);
    }
  }

  async function handleSave() {
    saving = true;
    try {
      const cleanPhones = phoneNumbers.map(p => p.trim()).filter(Boolean);
      const cleanBanks = bankAccounts
        .map(b => ({ bank_name: b.bank_name.trim(), account_number: b.account_number.trim() }))
        .filter(b => b.bank_name || b.account_number);
      const data = await api.settings.updateCompany({
        display_name: displayName,
        company_name: companyName,
        address,
        city,
        country,
        phone_numbers: cleanPhones,
        email,
        bank_accounts: cleanBanks,
        rccm,
        nif,
      });
      setCompanyInfo(data);
      showToast($t('company.saved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      saving = false;
    }
  }

  async function handleLogoUpload(event: CustomEvent<File>) {
    uploadingLogo = true;
    try {
      const data = await api.settings.uploadLogo(event.detail);
      setCompanyInfo(data);
      logoUrl = data.logo_url;
      showToast(get(t)('company.logoUploaded'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      uploadingLogo = false;
    }
  }

  async function handleLogoRemove() {
    try {
      const data = await api.settings.deleteLogo();
      setCompanyInfo(data);
      logoUrl = data.logo_url;
      showToast(get(t)('company.logoRemoved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    }
  }

  async function handleAddSignatory() {
    if (!newLabel.trim()) return;
    addingSignatory = true;
    try {
      const sig = await api.signatories.create({
        label: newLabel.trim(),
        name: newName.trim(),
        order: signatories.length,
      });
      // Upload signature image if one was selected
      if (newSignatureFile) {
        const updated = await api.signatories.uploadSignature(sig.id, newSignatureFile);
        signatories = [...signatories, updated];
      } else {
        signatories = [...signatories, sig];
      }
      newLabel = '';
      newName = '';
      newSignatureFile = null;
      showAddForm = false;
      showToast(get(t)('company.signatoryAdded'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      addingSignatory = false;
    }
  }

  async function handleSaveSignatory(sig: Signatory) {
    savingSignatoryId = sig.id;
    try {
      const updated = await api.signatories.update(sig.id, {
        label: sig.label,
        name: sig.name,
        order: sig.order,
      });
      signatories = signatories.map(s => s.id === updated.id ? updated : s);
      showToast(get(t)('company.signatoryUpdated'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      savingSignatoryId = null;
    }
  }

  async function handleDeleteSignatory(sig: Signatory) {
    if (!confirm(get(t)('company.signatoryDeleteConfirm'))) return;
    try {
      await api.signatories.remove(sig.id);
      signatories = signatories.filter(s => s.id !== sig.id);
      showToast(get(t)('company.signatoryDeleted'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    }
  }

  async function handleSignatureUploadFor(sig: Signatory, file: File) {
    uploadingSignatureFor = sig.id;
    try {
      const updated = await api.signatories.uploadSignature(sig.id, file);
      signatories = signatories.map(s => s.id === updated.id ? updated : s);
      showToast(get(t)('company.signatorySignatureUploaded'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      uploadingSignatureFor = null;
    }
  }

  async function handleSignatureRemoveFor(sig: Signatory) {
    try {
      const updated = await api.signatories.deleteSignature(sig.id);
      signatories = signatories.map(s => s.id === updated.id ? updated : s);
      showToast(get(t)('company.signatorySignatureRemoved'));
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    }
  }

  function onNewSignatureFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    newSignatureFile = input.files?.[0] ?? null;
  }

  function onSignatureFileChangeFor(sig: Signatory, event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) handleSignatureUploadFor(sig, file);
    input.value = '';
  }
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
        <h1 class="text-2xl font-bold text-white">{$t('company.title')}</h1>
        <p class="mt-1 text-sm" style="color: #9dd1f1">{$t('company.subtitle')}</p>
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
    <form on:submit|preventDefault={handleSave} class="space-y-6">

      <!-- ═══════════════════════════════════════════════ -->
      <!-- Card 1: Company Details                        -->
      <!-- ═══════════════════════════════════════════════ -->
      <div class="border border-gray-200 bg-white">
        <div class="divide-y divide-gray-100">
          <!-- Company Logo -->
          <div class="px-6 py-5">
            <label class="block text-sm font-medium text-gray-700">{$t('company.logo')}</label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.logoDescription')}
            </p>
            <div class="mt-3">
              <LogoUpload
                currentLogoUrl={logoUrl}
                uploading={uploadingLogo}
                on:upload={handleLogoUpload}
                on:remove={handleLogoRemove}
              />
            </div>
          </div>

          <!-- Display Name -->
          <div class="px-6 py-5">
            <label for="displayName" class="block text-sm font-medium text-gray-700">
              {$t('company.displayName')}
            </label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.displayNameHint')}
            </p>
            <input
              id="displayName"
              type="text"
              bind:value={displayName}
              placeholder="RealEstate"
              class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <!-- Company Name -->
          <div class="px-6 py-5">
            <label for="companyName" class="block text-sm font-medium text-gray-700">
              {$t('company.companyName')}
            </label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.companyNameHint')}
            </p>
            <input
              id="companyName"
              type="text"
              bind:value={companyName}
              placeholder="Your Company Name"
              class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <!-- Address -->
          <div class="px-6 py-5">
            <label for="address" class="block text-sm font-medium text-gray-700">
              {$t('company.address')}
            </label>
            <input
              id="address"
              type="text"
              bind:value={address}
              placeholder="123 Main Street"
              class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <!-- City + Country (side by side) -->
          <div class="px-6 py-5">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="city" class="block text-sm font-medium text-gray-700">{$t('company.city')}</label>
                <input
                  id="city"
                  type="text"
                  bind:value={city}
                  placeholder="N'Djaména"
                  class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                />
              </div>
              <div>
                <label for="country" class="block text-sm font-medium text-gray-700">{$t('company.country')}</label>
                <input
                  id="country"
                  type="text"
                  bind:value={country}
                  placeholder="Tchad"
                  class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          <!-- Phone Numbers -->
          <div class="px-6 py-5">
            <label class="block text-sm font-medium text-gray-700">{$t('company.phoneNumbers')}</label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.phoneHint')}
            </p>
            <div class="mt-2 space-y-2">
              {#each phoneNumbers as phone, i}
                <div class="flex items-center gap-2">
                  <input
                    type="text"
                    bind:value={phoneNumbers[i]}
                    placeholder="+235 XX XX XX"
                    class="block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                  />
                  {#if phoneNumbers.length > 1}
                    <button
                      type="button"
                      on:click={() => removePhone(i)}
                      class="flex h-9 w-9 flex-shrink-0 items-center justify-center border border-gray-200 text-gray-400 transition-colors hover:border-red-300 hover:bg-red-50 hover:text-red-500"
                      title={$t('common.remove')}
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  {/if}
                </div>
              {/each}
              <button
                type="button"
                on:click={addPhone}
                class="inline-flex items-center gap-1.5 border border-dashed border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700"
              >
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                {$t('company.addPhone')}
              </button>
            </div>
          </div>

          <!-- Email -->
          <div class="px-6 py-5">
            <label for="email" class="block text-sm font-medium text-gray-700">{$t('company.email')}</label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.emailHint')}
            </p>
            <input
              id="email"
              type="email"
              bind:value={email}
              placeholder="contact@company.com"
              class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <!-- Bank Accounts -->
          <div class="px-6 py-5">
            <label class="block text-sm font-medium text-gray-700">{$t('company.bankAccounts')}</label>
            <p class="mt-0.5 text-xs text-gray-400">
              {$t('company.bankHint')}
            </p>
            <div class="mt-2 space-y-2">
              {#each bankAccounts as bank, i}
                <div class="flex items-start gap-2">
                  <div class="grid flex-1 grid-cols-2 gap-2">
                    <input
                      type="text"
                      bind:value={bankAccounts[i].bank_name}
                      placeholder={$t('company.bankName')}
                      class="block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                    />
                    <input
                      type="text"
                      bind:value={bankAccounts[i].account_number}
                      placeholder={$t('company.accountNumber')}
                      class="block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                  {#if bankAccounts.length > 1}
                    <button
                      type="button"
                      on:click={() => removeBank(i)}
                      class="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center border border-gray-200 text-gray-400 transition-colors hover:border-red-300 hover:bg-red-50 hover:text-red-500"
                      title={$t('common.remove')}
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  {/if}
                </div>
              {/each}
              <button
                type="button"
                on:click={addBank}
                class="inline-flex items-center gap-1.5 border border-dashed border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700"
              >
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                {$t('company.addBank')}
              </button>
            </div>
          </div>

          <!-- Legal References (RCCM + NIF) -->
          <div class="px-6 py-5">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="rccm" class="block text-sm font-medium text-gray-700">{$t('company.rccm')}</label>
                <p class="mt-0.5 text-xs text-gray-400">
                  {$t('company.rccmHint')}
                </p>
                <input
                  id="rccm"
                  type="text"
                  bind:value={rccm}
                  placeholder="RCCM/NDJ/..."
                  class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                />
              </div>
              <div>
                <label for="nif" class="block text-sm font-medium text-gray-700">{$t('company.nif')}</label>
                <p class="mt-0.5 text-xs text-gray-400">
                  {$t('company.nifHint')}
                </p>
                <input
                  id="nif"
                  type="text"
                  bind:value={nif}
                  placeholder="NIF..."
                  class="mt-2 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          <!-- Signatories -->
          <div class="px-6 py-5">
            <div class="flex items-center justify-between">
              <div>
                <label class="block text-sm font-medium text-gray-700">{$t('company.signatories')}</label>
                <p class="mt-0.5 text-xs text-gray-400">{$t('company.signatoriesHint')}</p>
              </div>
            </div>

            {#if loadingSignatories}
              <div class="mt-3 flex justify-center py-4">
                <svg class="h-5 w-5 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            {:else}
              <div class="mt-3 space-y-3">
                {#each signatories as sig (sig.id)}
                  <!-- Existing signatory row -->
                  <div class="border border-gray-200 bg-gray-50/40 p-4">
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs font-medium text-gray-600">{$t('company.signatoryLabel')}</label>
                        <input
                          type="text"
                          bind:value={sig.label}
                          placeholder={$t('company.signatoryLabelPlaceholder')}
                          class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-600">{$t('company.signatoryName')}</label>
                        <input
                          type="text"
                          bind:value={sig.name}
                          placeholder={$t('company.signatoryNamePlaceholder')}
                          class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                    </div>

                    <!-- Signature image -->
                    <div class="mt-3">
                      {#if sig.signature_url}
                        <div class="flex items-center gap-3">
                          <div class="flex h-12 w-36 items-center justify-center border border-gray-200 bg-white p-1.5">
                            <img src={mediaUrl(sig.signature_url)} alt="Signature" class="max-h-9 max-w-full object-contain" />
                          </div>
                          <button
                            type="button"
                            on:click={() => handleSignatureRemoveFor(sig)}
                            class="text-xs text-red-500 hover:text-red-700 underline"
                          >
                            {$t('common.remove')}
                          </button>
                        </div>
                      {:else}
                        <label class="flex cursor-pointer items-center gap-2 border border-dashed border-gray-300 px-3 py-2 text-xs font-medium text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700 w-fit {uploadingSignatureFor === sig.id ? 'pointer-events-none opacity-60' : ''}">
                          {#if uploadingSignatureFor === sig.id}
                            <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                          {:else}
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                            </svg>
                          {/if}
                          {$t('common.upload')}
                          <input type="file" accept="image/png,image/jpeg,image/webp" class="sr-only"
                            on:change={(e) => onSignatureFileChangeFor(sig, e)} />
                        </label>
                      {/if}
                    </div>

                    <!-- Row actions -->
                    <div class="mt-3 flex items-center justify-between">
                      <button
                        type="button"
                        on:click={() => handleDeleteSignatory(sig)}
                        class="inline-flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700"
                      >
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        {$t('common.delete')}
                      </button>
                      <button
                        type="button"
                        on:click={() => handleSaveSignatory(sig)}
                        disabled={savingSignatoryId === sig.id}
                        class="inline-flex items-center gap-1.5 bg-primary-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
                      >
                        {#if savingSignatoryId === sig.id}
                          <svg class="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        {/if}
                        {$t('common.save')}
                      </button>
                    </div>
                  </div>
                {/each}

                {#if signatories.length === 0 && !showAddForm}
                  <p class="border border-dashed border-gray-200 px-4 py-5 text-center text-sm text-gray-400">
                    {$t('company.noSignatories')}
                  </p>
                {/if}

                <!-- Add signatory form -->
                {#if showAddForm}
                  <div class="border border-primary-200 bg-primary-50/30 p-4">
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs font-medium text-gray-600">{$t('company.signatoryLabel')} <span class="text-red-400">*</span></label>
                        <input
                          type="text"
                          bind:value={newLabel}
                          placeholder={$t('company.signatoryLabelPlaceholder')}
                          class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-600">{$t('company.signatoryName')}</label>
                        <input
                          type="text"
                          bind:value={newName}
                          placeholder={$t('company.signatoryNamePlaceholder')}
                          class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                    </div>
                    {#if newSignatureFile}
                      <p class="mt-2 text-xs text-primary-600">{newSignatureFile.name}</p>
                    {/if}
                    <div class="mt-3 flex items-center gap-2">
                      <label class="flex cursor-pointer items-center gap-1.5 border border-dashed border-gray-300 px-2.5 py-1.5 text-xs text-gray-500 hover:border-gray-400">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        {$t('common.upload')}
                        <input type="file" accept="image/png,image/jpeg,image/webp" class="sr-only" on:change={onNewSignatureFileChange} />
                      </label>
                      <div class="flex-1"></div>
                      <button type="button" on:click={() => { showAddForm = false; newLabel = ''; newName = ''; newSignatureFile = null; }}
                        class="border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                        {$t('common.cancel')}
                      </button>
                      <button
                        type="button"
                        on:click={handleAddSignatory}
                        disabled={addingSignatory || !newLabel.trim()}
                        class="inline-flex items-center gap-1.5 bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                      >
                        {#if addingSignatory}
                          <svg class="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        {/if}
                        {$t('company.addSignatory')}
                      </button>
                    </div>
                  </div>
                {/if}

                <!-- Add button (shown when form is not visible) -->
                {#if !showAddForm}
                  <button
                    type="button"
                    on:click={() => (showAddForm = true)}
                    class="inline-flex items-center gap-1.5 border border-dashed border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700"
                  >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                    {$t('company.addSignatory')}
                  </button>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════ -->
      <!-- Invoice Settings link                          -->
      <!-- ═══════════════════════════════════════════════ -->
      <a
        href="/admin/invoice-settings"
        class="block border border-gray-200 bg-white px-6 py-4 transition-colors hover:bg-gray-50"
      >
        <span class="text-sm font-medium text-gray-900">{$t('admin.invoiceSettings.title')}</span>
        <p class="text-xs text-gray-500">{$t('admin.invoiceSettings.description')}</p>
      </a>

      <!-- ═══════════════════════════════════════════════ -->
      <!-- Save / Reset buttons                           -->
      <!-- ═══════════════════════════════════════════════ -->
      <div class="flex items-center justify-end gap-3">
        <button
          type="button"
          on:click={handleReset}
          class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          {$t('common.reset')}
        </button>
        <button
          type="submit"
          disabled={saving}
          class="inline-flex items-center gap-2 bg-primary-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:opacity-50"
        >
          {#if saving}
            <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          {/if}
          {$t('common.saveChanges')}
        </button>
      </div>

    </form>
  {/if}
</div>

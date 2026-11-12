<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n'; import { get } from 'svelte/store';
  import { api } from '$lib/api/client';
  import type { User, UserCreatePayload, UserUpdatePayload } from '$lib/api/types';
  import DataTable from '$lib/components/DataTable.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import Badge from '$lib/components/Badge.svelte';
  import { ROLE_COLORS, ROLE_LABELS } from '$lib/utils/status';

  // ── List state ──
  let users: User[] = [];
  let loading = true;
  let page = 1;
  let count = 0;
  const pageSize = 25;

  // ── Panel state ──
  let panelOpen = false;
  let panelMode: 'create' | 'edit' = 'create';
  let selectedUser: User | null = null;
  let saving = false;
  let deleting = false;

  // ── Form state ──
  let form = {
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    role: 'read_only' as User['role'],
    is_active: true,
    password: ''
  };
  let errors: Record<string, string[]> = {};

  // ── Password reset ──
  let showPasswordReset = false;
  let newPassword = '';
  let savingPassword = false;

  // ── Toast ──
  let toast: { message: string; type: 'success' | 'error' } | null = null;
  let toastTimeout: ReturnType<typeof setTimeout>;

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast = { message, type };
    toastTimeout = setTimeout(() => (toast = null), 5000);
  }

  // ── Load ──
  async function loadUsers() {
    loading = true;
    try {
      const res = await api.users.list(`page=${page}&page_size=${pageSize}`);
      users = res.results;
      count = res.count;
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.errorLoading'), 'error');
    } finally {
      loading = false;
    }
  }

  onMount(loadUsers);

  function onPageChange(newPage: number) {
    page = newPage;
    loadUsers();
  }

  // ── Panel helpers ──
  function openCreatePanel() {
    panelMode = 'create';
    selectedUser = null;
    form = {
      username: '',
      email: '',
      first_name: '',
      last_name: '',
      role: 'read_only',
      is_active: true,
      password: ''
    };
    errors = {};
    showPasswordReset = false;
    newPassword = '';
    panelOpen = true;
  }

  function openEditPanel(user: User) {
    panelMode = 'edit';
    selectedUser = user;
    form = {
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      is_active: user.is_active,
      password: ''
    };
    errors = {};
    showPasswordReset = false;
    newPassword = '';
    panelOpen = true;
  }

  function closePanel() {
    panelOpen = false;
    selectedUser = null;
    errors = {};
    showPasswordReset = false;
    newPassword = '';
  }

  // ── Save (create or update) ──
  async function saveUser() {
    saving = true;
    errors = {};
    try {
      if (panelMode === 'create') {
        const payload: UserCreatePayload = {
          username: form.username,
          email: form.email,
          first_name: form.first_name,
          last_name: form.last_name,
          role: form.role,
          password: form.password
        };
        await api.users.create(payload);
        showToast(get(t)('users.created'));
      } else if (selectedUser) {
        const payload: UserUpdatePayload = {
          username: form.username,
          email: form.email,
          first_name: form.first_name,
          last_name: form.last_name,
          role: form.role,
          is_active: form.is_active
        };
        await api.users.update(selectedUser.id, payload);
        showToast(get(t)('users.updated'));
      }
      closePanel();
      await loadUsers();
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'data' in e) {
        const data = (e as { data?: unknown }).data;
        if (typeof data === 'object' && data !== null && !('detail' in data)) {
          errors = data as Record<string, string[]>;
        }
      }
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      saving = false;
    }
  }

  // ── Delete ──
  async function deleteUser() {
    if (!selectedUser) return;
    if (!confirm(get(t)('users.deactivateConfirm2', { values: { username: selectedUser.username } }))) return;

    deleting = true;
    try {
      await api.users.delete(selectedUser.id);
      showToast(get(t)('users.deactivated'));
      closePanel();
      await loadUsers();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      deleting = false;
    }
  }

  // ── Reset password ──
  async function resetPassword() {
    if (!selectedUser || !newPassword) return;
    savingPassword = true;
    try {
      const res = await api.users.setPassword(selectedUser.id, newPassword);
      showToast(res.detail || get(t)('users.passwordUpdated'));
      newPassword = '';
      showPasswordReset = false;
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : get(t)('common.somethingWentWrong'), 'error');
    } finally {
      savingPassword = false;
    }
  }

  const ROLE_OPTIONS: { value: User['role']; labelKey: string }[] = [
    { value: 'admin', labelKey: 'status.role.admin' },
    { value: 'manager', labelKey: 'status.role.manager' },
    { value: 'accountant', labelKey: 'status.role.accountant' },
    { value: 'agent', labelKey: 'status.role.agent' },
    { value: 'read_only', labelKey: 'status.role.read_only' }
  ];
</script>

<div class="space-y-4">
  <!-- Hero -->
  <div class="px-6 py-5" style="background: #031927">
    <div class="flex items-start justify-between gap-4">
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
          <h1 class="text-2xl font-bold text-white">{$t('users.title')}</h1>
          <p class="mt-1 text-sm" style="color: #9dd1f1">{$t('users.usersTotal', { values: { count } })}</p>
        </div>
      </div>
      <div class="flex-shrink-0">
        <button
          on:click={openCreatePanel}
          class="btn-on-dark"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {$t('users.addUser')}
        </button>
      </div>
    </div>
  </div>

  <!-- Toast -->
  {#if toast}
    <div
      class="fixed top-4 right-4 z-[60] flex items-center gap-3 px-4 py-3 transition-all {toast.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}"
    >
      <!-- The message text states the outcome; the icon only repeated it. -->
      <span class="text-sm font-medium">{toast.message}</span>
      <button on:click={() => (toast = null)} class="ml-2 text-current opacity-50 hover:opacity-100">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  {/if}

  <!-- Table -->
  <DataTable {loading} empty={!loading && users.length === 0} emptyMessage={$t('users.noUsers')}>
    <tr slot="head">
      <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">{$t('users.username')}</th>
      <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">{$t('users.email')}</th>
      <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">{$t('common.name')}</th>
      <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">{$t('users.role')}</th>
      <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">{$t('common.status')}</th>
    </tr>

    {#each users as user (user.id)}
      <tr
        class="cursor-pointer hover:bg-gray-50 transition-colors"
        on:click={() => openEditPanel(user)}
      >
        <td class="px-4 py-3 font-medium text-gray-900">{user.username}</td>
        <td class="px-4 py-3 text-gray-600">{user.email}</td>
        <td class="px-4 py-3 text-gray-600">
          {[user.first_name, user.last_name].filter(Boolean).join(' ') || '—'}
        </td>
        <td class="px-4 py-3">
          <Badge variant={ROLE_COLORS[user.role] ?? 'gray'} label={ROLE_LABELS[user.role] ?? user.role} />
        </td>
        <td class="px-4 py-3">
          {#if user.is_active}
            <Badge variant="green" label={$t('common.active')} />
          {:else}
            <Badge variant="red" label={$t('common.inactive')} />
          {/if}
        </td>
      </tr>
    {/each}
  </DataTable>

  <Pagination {page} {count} {pageSize} on:change={(e) => onPageChange(e.detail)} />
</div>

<!-- ─── Slide-over panel ─────────────────────────────────────────────── -->
{#if panelOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
    <!-- Backdrop -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="absolute inset-0 bg-slate-900/30" on:click={closePanel}></div>

    <!-- Panel -->
    <div class="relative flex h-full w-full max-w-lg flex-col bg-white">
      <!-- Header -->
      <div class="flex-shrink-0 border-b border-gray-200 px-6 py-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-semibold text-gray-900">
              {panelMode === 'create' ? $t('users.addUser') : $t('users.editUser')}
            </h2>
            <p class="text-sm text-gray-500">
              {panelMode === 'create'
                ? $t('users.newUser')
                : selectedUser?.username ?? ''}
            </p>
          </div>
          <button
            on:click={closePanel}
            class="p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Body (scrollable) -->
      <div class="flex-1 overflow-y-auto px-6 py-5">
        <form id="user-form" on:submit|preventDefault={saveUser} class="space-y-5">
          <!-- Username -->
          <div>
            <label for="username" class="block text-sm font-medium text-gray-700">{$t('users.username')}</label>
            <input
              id="username"
              type="text"
              bind:value={form.username}
              required
              class="mt-1 block w-full border px-3 py-2 text-sm focus:outline-none focus:ring-1 {errors.username ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300 focus:border-[#508aa8] focus:ring-[#508aa8]'}"
            />
            {#if errors.username}
              <p class="mt-1 text-xs text-red-600">{errors.username[0]}</p>
            {/if}
          </div>

          <!-- Email -->
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700">{$t('users.email')}</label>
            <input
              id="email"
              type="email"
              bind:value={form.email}
              class="mt-1 block w-full border px-3 py-2 text-sm focus:outline-none focus:ring-1 {errors.email ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300 focus:border-[#508aa8] focus:ring-[#508aa8]'}"
            />
            {#if errors.email}
              <p class="mt-1 text-xs text-red-600">{errors.email[0]}</p>
            {/if}
          </div>

          <!-- First Name + Last Name -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label for="first_name" class="block text-sm font-medium text-gray-700">{$t('users.firstName')}</label>
              <input
                id="first_name"
                type="text"
                bind:value={form.first_name}
                class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-[#508aa8] focus:outline-none focus:ring-1 focus:ring-[#508aa8]"
              />
            </div>
            <div>
              <label for="last_name" class="block text-sm font-medium text-gray-700">{$t('users.lastName')}</label>
              <input
                id="last_name"
                type="text"
                bind:value={form.last_name}
                class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-[#508aa8] focus:outline-none focus:ring-1 focus:ring-[#508aa8]"
              />
            </div>
          </div>

          <!-- Role -->
          <div>
            <label for="role" class="block text-sm font-medium text-gray-700">{$t('users.role')}</label>
            <select
              id="role"
              bind:value={form.role}
              class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-[#508aa8] focus:outline-none focus:ring-1 focus:ring-[#508aa8]"
            >
              {#each ROLE_OPTIONS as opt}
                <option value={opt.value}>{$t(opt.labelKey)}</option>
              {/each}
            </select>
            {#if errors.role}
              <p class="mt-1 text-xs text-red-600">{errors.role[0]}</p>
            {/if}
          </div>

          <!-- Active toggle (edit mode only) -->
          {#if panelMode === 'edit'}
            <div class="flex items-center justify-between border border-gray-200 bg-gray-50 px-4 py-3">
              <div>
                <span class="text-sm font-medium text-gray-700">{$t('users.isActive')}</span>
                <p class="text-xs text-gray-500">{$t('users.inactiveHint')}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={form.is_active}
                on:click={() => (form.is_active = !form.is_active)}
                class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 {form.is_active ? 'bg-[#508aa8]' : 'bg-gray-200'}"
              >
                <span
                  class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white ring-0 transition duration-200 ease-in-out {form.is_active ? 'translate-x-5' : 'translate-x-0'}"
                ></span>
              </button>
            </div>
          {/if}

          <!-- Password (create mode only) -->
          {#if panelMode === 'create'}
            <div>
              <label for="password" class="block text-sm font-medium text-gray-700">{$t('users.password')}</label>
              <input
                id="password"
                type="password"
                bind:value={form.password}
                required
                minlength="8"
                class="mt-1 block w-full border px-3 py-2 text-sm focus:outline-none focus:ring-1 {errors.password ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300 focus:border-[#508aa8] focus:ring-[#508aa8]'}"
              />
              {#if errors.password}
                <p class="mt-1 text-xs text-red-600">{errors.password[0]}</p>
              {:else}
                <p class="mt-1 text-xs text-gray-400">{$t('users.minimumChars')}</p>
              {/if}
            </div>
          {/if}
        </form>

        <!-- Password reset section (edit mode only) -->
        {#if panelMode === 'edit' && selectedUser}
          <div class="mt-6 border-t border-gray-200 pt-5">
            <button
              type="button"
              on:click={() => (showPasswordReset = !showPasswordReset)}
              class="flex w-full items-center justify-between text-sm font-medium text-gray-700 hover:text-gray-900"
            >
              <span>{$t('users.resetPassword')}</span>
              <svg
                class="h-4 w-4 transition-transform {showPasswordReset ? 'rotate-180' : ''}"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {#if showPasswordReset}
              <div class="mt-3 space-y-3">
                <div>
                  <label for="new-password" class="block text-sm font-medium text-gray-700">{$t('users.password')}</label>
                  <input
                    id="new-password"
                    type="password"
                    bind:value={newPassword}
                    minlength="8"
                    placeholder={$t('users.minimumChars')}
                    class="mt-1 block w-full border border-gray-300 px-3 py-2 text-sm focus:border-[#508aa8] focus:outline-none focus:ring-1 focus:ring-[#508aa8]"
                  />
                </div>
                <button
                  type="button"
                  on:click={resetPassword}
                  disabled={savingPassword || newPassword.length < 8}
                  class="btn-primary"
                >
                  {#if savingPassword}
                    <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                  {/if}
                  {$t('common.save')}
                </button>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex-shrink-0 border-t border-gray-200 bg-gray-50 px-6 py-4">
        <div class="flex items-center {panelMode === 'edit' ? 'justify-between' : 'justify-end gap-3'}">
          {#if panelMode === 'edit'}
            <!-- Deactivate (left side) -->
            <button
              type="button"
              on:click={deleteUser}
              disabled={deleting}
              class="inline-flex items-center gap-2 border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 transition-colors"
            >
              {#if deleting}
                <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              {:else}
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              {/if}
              {$t('users.deactivate')}
            </button>
          {/if}

          <div class="flex items-center gap-3">
            <button
              type="button"
              on:click={closePanel}
              class="border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {$t('common.cancel')}
            </button>
            <button
              type="submit"
              form="user-form"
              disabled={saving}
              class="inline-flex items-center gap-2 bg-[#508aa8] px-4 py-2 text-sm font-medium text-white hover:bg-[#3d6f87] focus:outline-none focus:ring-2 focus:ring-[#508aa8] focus:ring-offset-2 disabled:opacity-50 transition-colors"
            >
              {#if saving}
                <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              {/if}
              {panelMode === 'create' ? $t('users.addUser') : $t('common.saveChanges')}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

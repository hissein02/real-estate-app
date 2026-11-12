<script lang="ts">
  import { t } from 'svelte-i18n';

  // Settings index: a list of destinations. No icons, no per-item accent colour —
  // the section names carry the meaning.
  const sections = [
    { titleKey: 'admin.users.title', descriptionKey: 'admin.users.description', href: '/admin/users' },
    { titleKey: 'admin.scheduledTasks.title', descriptionKey: 'admin.scheduledTasks.description', href: '/admin/scheduled-tasks' },
    { titleKey: 'admin.company.title', descriptionKey: 'admin.company.description', href: '/admin/company' },
    { titleKey: 'admin.invoiceSettings.title', descriptionKey: 'admin.invoiceSettings.description', href: '/admin/invoice-settings' },
    { titleKey: 'admin.notifications.title', descriptionKey: 'admin.notifications.description', href: '/admin/notifications' },
    { titleKey: 'admin.preferences.title', descriptionKey: 'admin.preferences.description', href: '/admin/preferences' }
  ];
</script>

<div class="space-y-4">
  <div class="px-6 py-5" style="background: #031927">
    <h1 class="text-2xl font-bold text-white">{$t('admin.title')}</h1>
    <p class="mt-1 text-sm" style="color: #9dd1f1">{$t('admin.subtitle')}</p>
  </div>

  <div class="border border-gray-200 bg-white">
    {#each sections as section, i}
      <a
        href={section.href}
        class="block px-5 py-4 hover:bg-gray-50 {i > 0 ? 'border-t border-gray-200' : ''}"
      >
        <h2 class="text-sm font-semibold text-gray-900">{$t(section.titleKey)}</h2>
        <p class="mt-0.5 text-xs leading-relaxed text-gray-500">{$t(section.descriptionKey)}</p>
      </a>
    {/each}
  </div>
</div>

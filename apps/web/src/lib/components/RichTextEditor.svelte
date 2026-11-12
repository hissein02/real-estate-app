<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import type { Readable } from 'svelte/store';
  import { createEditor, EditorContent } from 'svelte-tiptap';
  import type { Editor } from 'svelte-tiptap';
  import { Extension } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Underline from '@tiptap/extension-underline';

  /**
   * Enter inserts a <br> instead of opening a new <p>.
   *
   * These templates are rendered inside an email body, where a line break is
   * what people expect from Enter. Inside a list Enter must still create the
   * next item, so the shortcut defers to the default there.
   */
  const EnterAsHardBreak = Extension.create({
    name: 'enterAsHardBreak',
    addKeyboardShortcuts() {
      const hardBreak = () => {
        if (
          this.editor.isActive('bulletList') ||
          this.editor.isActive('orderedList') ||
          this.editor.isActive('codeBlock')
        ) {
          return false; // let the default handler run
        }
        return this.editor.commands.setHardBreak();
      };
      return { Enter: hardBreak, 'Shift-Enter': hardBreak };
    }
  });

  export let content: string = '';

  const dispatch = createEventDispatcher<{ change: string }>();

  let editor: Readable<Editor>;

  onMount(() => {
    editor = createEditor({
      extensions: [StarterKit, Underline, EnterAsHardBreak],
      content,
      onUpdate: ({ editor: e }) => {
        dispatch('change', e.getHTML());
      }
    });
  });

  function toggleBold() {
    $editor?.chain().focus().toggleBold().run();
  }
  function toggleItalic() {
    $editor?.chain().focus().toggleItalic().run();
  }
  function toggleUnderline() {
    $editor?.chain().focus().toggleUnderline().run();
  }
  function toggleBulletList() {
    $editor?.chain().focus().toggleBulletList().run();
  }
  function toggleOrderedList() {
    $editor?.chain().focus().toggleOrderedList().run();
  }

  $: isBold = $editor?.isActive('bold') ?? false;
  $: isItalic = $editor?.isActive('italic') ?? false;
  $: isUnderline = $editor?.isActive('underline') ?? false;
  $: isBulletList = $editor?.isActive('bulletList') ?? false;
  $: isOrderedList = $editor?.isActive('orderedList') ?? false;
</script>

<div class="border border-gray-300 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500 overflow-hidden">
  <!-- Toolbar -->
  {#if $editor}
    <div class="flex items-center gap-0.5 border-b border-gray-200 bg-gray-50 px-2 py-1.5">
      <!-- Bold -->
      <button
        type="button"
        on:click={toggleBold}
        class="inline-flex items-center justify-center p-1.5 text-sm transition-colors {isBold ? 'bg-primary-100 text-primary-800' : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'}"
        title="Bold (Ctrl+B)"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M15.6 10.79c.97-.67 1.65-1.77 1.65-2.79 0-2.26-1.75-4-4-4H7v14h7.04c2.09 0 3.71-1.7 3.71-3.79 0-1.52-.86-2.82-2.15-3.42zM10 6.5h3c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-3v-3zm3.5 9H10v-3h3.5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5z" />
        </svg>
      </button>

      <!-- Italic -->
      <button
        type="button"
        on:click={toggleItalic}
        class="inline-flex items-center justify-center p-1.5 text-sm transition-colors {isItalic ? 'bg-primary-100 text-primary-800' : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'}"
        title="Italic (Ctrl+I)"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M10 4v3h2.21l-3.42 8H6v3h8v-3h-2.21l3.42-8H18V4z" />
        </svg>
      </button>

      <!-- Underline -->
      <button
        type="button"
        on:click={toggleUnderline}
        class="inline-flex items-center justify-center p-1.5 text-sm transition-colors {isUnderline ? 'bg-primary-100 text-primary-800' : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'}"
        title="Underline (Ctrl+U)"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 17c3.31 0 6-2.69 6-6V3h-2.5v8c0 1.93-1.57 3.5-3.5 3.5S8.5 12.93 8.5 11V3H6v8c0 3.31 2.69 6 6 6zm-7 2v2h14v-2H5z" />
        </svg>
      </button>

      <!-- Divider -->
      <div class="mx-1 h-5 w-px bg-gray-300"></div>

      <!-- Bullet list -->
      <button
        type="button"
        on:click={toggleBulletList}
        class="inline-flex items-center justify-center p-1.5 text-sm transition-colors {isBulletList ? 'bg-primary-100 text-primary-800' : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'}"
        title="Bullet List"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M4 10.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm0-6c-.83 0-1.5.67-1.5 1.5S3.17 7.5 4 7.5 5.5 6.83 5.5 6 4.83 4.5 4 4.5zm0 12c-.83 0-1.5.68-1.5 1.5s.68 1.5 1.5 1.5 1.5-.68 1.5-1.5-.67-1.5-1.5-1.5zM7 19h14v-2H7v2zm0-6h14v-2H7v2zm0-8v2h14V5H7z" />
        </svg>
      </button>

      <!-- Ordered list -->
      <button
        type="button"
        on:click={toggleOrderedList}
        class="inline-flex items-center justify-center p-1.5 text-sm transition-colors {isOrderedList ? 'bg-primary-100 text-primary-800' : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'}"
        title="Numbered List"
      >
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M2 17h2v.5H3v1h1v.5H2v1h3v-4H2v1zm1-9h1V4H2v1h1v3zm-1 3h1.8L2 13.1v.9h3v-1H3.2L5 10.9V10H2v1zm5-6v2h14V5H7zm0 14h14v-2H7v2zm0-6h14v-2H7v2z" />
        </svg>
      </button>
    </div>
  {/if}

  <!-- Editor content area -->
  <div class="tiptap-editor">
    {#if $editor}
      <EditorContent editor={$editor} />
    {/if}
  </div>
</div>

<style>
  .tiptap-editor :global(.tiptap) {
    padding: 0.5rem 0.75rem;
    min-height: 12rem;
    max-height: 24rem;
    overflow-y: auto;
    outline: none;
    font-size: 0.875rem;
    line-height: 1.625;
    color: #1f2937;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
      'Courier New', monospace;
  }

  .tiptap-editor :global(.tiptap p) {
    margin: 0.25em 0;
  }

  /* Without this a trailing <br> collapses and the caret appears not to move. */
  .tiptap-editor :global(.tiptap br) {
    content: '';
    display: block;
  }

  .tiptap-editor :global(.tiptap p:first-child) {
    margin-top: 0;
  }

  .tiptap-editor :global(.tiptap p:last-child) {
    margin-bottom: 0;
  }

  .tiptap-editor :global(.tiptap strong) {
    font-weight: 700;
  }

  .tiptap-editor :global(.tiptap em) {
    font-style: italic;
  }

  .tiptap-editor :global(.tiptap u) {
    text-decoration: underline;
  }

  .tiptap-editor :global(.tiptap ul) {
    list-style-type: disc;
    padding-left: 1.5em;
    margin: 0.25em 0;
  }

  .tiptap-editor :global(.tiptap ol) {
    list-style-type: decimal;
    padding-left: 1.5em;
    margin: 0.25em 0;
  }

  .tiptap-editor :global(.tiptap li) {
    margin: 0.125em 0;
  }

  .tiptap-editor :global(.tiptap p.is-editor-empty:first-child::before) {
    content: attr(data-placeholder);
    float: left;
    color: #9ca3af;
    pointer-events: none;
    height: 0;
  }
</style>

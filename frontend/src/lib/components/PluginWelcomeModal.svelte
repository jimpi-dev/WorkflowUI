<script lang="ts">
	import { onMount } from 'svelte';

	const STORAGE_KEY = 'workflowui_plugin_welcome_seen';

	const COMFYUI_REGISTRY_URL = 'https://registry.comfy.org/publishers/jimpi/nodes/WorkflowUIPlugin';
	const GITHUB_URL = 'https://github.com/jimpi-dev/WorkflowUIPlugin';

	let open = $state(false);

	onMount(() => {
		if (typeof window === 'undefined') return;
		const seen = localStorage.getItem(STORAGE_KEY);
		if (!seen) {
			open = true;
		}
	});

	function dismiss() {
		if (typeof window !== 'undefined') {
			localStorage.setItem(STORAGE_KEY, '1');
		}
		open = false;
	}

	function handleBackdropClick(e: MouseEvent) {
		if ((e.target as HTMLElement).hasAttribute('data-backdrop')) dismiss();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') dismiss();
	}
</script>

{#if open}
	<div
		class="plugin-welcome-backdrop"
		role="dialog"
		aria-modal="true"
		aria-labelledby="plugin-welcome-title"
		aria-describedby="plugin-welcome-desc"
		data-backdrop
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
		tabindex="-1"
	>
		<div
			class="plugin-welcome-card"
			role="presentation"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="plugin-welcome-title" class="plugin-welcome-title">
				Install the WorkflowUI plugin for ComfyUI
			</h2>
			<p id="plugin-welcome-desc" class="plugin-welcome-intro">
				For the best experience and full feature set, its recommended installing the
				<strong>WorkflowUI Plugin</strong> in ComfyUI. It adds integration APIs and a custom node so the app can work seamlessly with your workflows.
			</p>

			<div class="plugin-welcome-features">
				<p class="plugin-welcome-features-heading">These features only work when the plugin is running in ComfyUI:</p>
				<ul>
					<li><strong>WorkflowUI Link schema</strong> — When you import a workflow that contains the WorkflowUI Link node, the app builds the form from your node’s field definitions (types and labels) instead of inferring from the whole graph.</li>
					<li><strong>Media APIs</strong> — Delete, view, list, and version outputs via the backend for consistent handling of run outputs.</li>
					<li><strong>Send to app</strong> — Prefill the app with outputs from a previous run (references resolved via ComfyUI/plugin storage).</li>
				</ul>
			</div>

			<div class="plugin-welcome-links">
				<p class="plugin-welcome-links-heading">Install:</p>
				<ul class="plugin-welcome-link-list">
					<li>
						<a href={COMFYUI_REGISTRY_URL} target="_blank" rel="noopener noreferrer">
							ComfyUI Registry
						</a>
						<span class="plugin-welcome-link-hint">— install via the manager</span>
					</li>
					<li>
						<a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
							GitHub
						</a>
						<span class="plugin-welcome-link-hint">— source and API details</span>
					</li>
				</ul>
				<p class="plugin-welcome-install-note">Put the plugin in <code>ComfyUI/custom_nodes/</code> and restart ComfyUI.</p>
			</div>

			<div class="plugin-welcome-actions">
				<button type="button" class="plugin-welcome-btn primary" onclick={dismiss}>
					Got it
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.plugin-welcome-backdrop {
		position: fixed;
		inset: 0;
		z-index: 100001;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in srgb, var(--bg, #0d0d0d) 60%, transparent);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		animation: plugin-welcome-fade-in 0.2s ease-out;
		padding: 1rem;
	}

	.plugin-welcome-card {
		background: color-mix(in srgb, var(--card, #1a1a1a) 98%, transparent);
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
		border-radius: 16px;
		box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
		max-width: 32rem;
		max-height: 90vh;
		overflow-y: auto;
		padding: 1.75rem 2rem;
	}

	.plugin-welcome-title {
		margin: 0 0 0.75rem;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text);
		letter-spacing: -0.02em;
	}

	.plugin-welcome-intro {
		margin: 0 0 1.25rem;
		font-size: 0.95rem;
		line-height: 1.5;
		color: var(--muted);
	}

	.plugin-welcome-intro strong {
		color: var(--text);
	}

	.plugin-welcome-features {
		margin-bottom: 1.25rem;
	}

	.plugin-welcome-features-heading,
	.plugin-welcome-links-heading {
		margin: 0 0 0.5rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text);
	}

	.plugin-welcome-features ul {
		margin: 0;
		padding-left: 1.25rem;
		font-size: 0.9rem;
		line-height: 1.55;
		color: var(--muted);
	}

	.plugin-welcome-features li {
		margin-bottom: 0.5rem;
	}

	.plugin-welcome-features li:last-child {
		margin-bottom: 0;
	}

	.plugin-welcome-links {
		margin-bottom: 1.5rem;
	}

	.plugin-welcome-link-list {
		margin: 0 0 0.75rem;
		padding-left: 1.25rem;
		font-size: 0.9rem;
		color: var(--muted);
	}

	.plugin-welcome-link-list li {
		margin-bottom: 0.35rem;
	}

	.plugin-welcome-link-list a {
		color: var(--accent);
		text-decoration: none;
		font-weight: 500;
	}

	.plugin-welcome-link-list a:hover {
		text-decoration: underline;
	}

	.plugin-welcome-link-hint {
		font-size: 0.85rem;
		opacity: 0.9;
	}

	.plugin-welcome-install-note {
		margin: 0;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.plugin-welcome-install-note code {
		background: color-mix(in srgb, var(--accent) 15%, transparent);
		padding: 0.15em 0.4em;
		border-radius: 4px;
		font-size: 0.9em;
	}

	.plugin-welcome-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.plugin-welcome-btn {
		padding: 0.5rem 1.25rem;
		font-size: 0.95rem;
		font-weight: 500;
		border-radius: 8px;
		border: none;
		cursor: pointer;
	}

	.plugin-welcome-btn.primary {
		background: var(--accent);
		color: var(--accent-contrast, #fff);
	}

	.plugin-welcome-btn.primary:hover {
		background: var(--accent-hover);
	}

	@keyframes plugin-welcome-fade-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>

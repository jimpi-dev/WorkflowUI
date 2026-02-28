<script lang="ts">
	import { getContrastForeground } from '$lib/utils/color';

	let {
		appHeaderColor = undefined as string | null | undefined,
		label = 'App',
		title = '',
		removed = false
	}: {
		appHeaderColor?: string | null;
		label?: string;
		title?: string;
		removed?: boolean;
	} = $props();

	let contrast = $derived(appHeaderColor ? getContrastForeground(appHeaderColor) : 'light');
</script>

<span
	class="run-app-badge run-app-badge-contrast-{contrast}"
	class:run-app-badge-removed={removed}
	style={appHeaderColor
		? `--run-app-badge-color: ${appHeaderColor}`
		: '--run-app-badge-color: var(--accent)'}
	title={title || label}
>
	{label}
</span>

<style>
	.run-app-badge {
		--run-app-badge-color: var(--accent);
		display: inline-flex;
		align-items: center;
		padding: 0.2rem 0.5rem;
		font-size: 0.7rem;
		font-weight: 600;
		border-radius: 4px;
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		background: color-mix(in srgb, var(--run-app-badge-color) 18%, transparent);
		border: 1px solid color-mix(in srgb, var(--run-app-badge-color) 50%, transparent);
		color: var(--run-app-badge-color);
	}

	:global([data-theme="light"]) .run-app-badge {
		background: var(--run-app-badge-color);
		border: 1px solid color-mix(in srgb, var(--run-app-badge-color) 65%, black);
	}
	:global([data-theme="light"]) .run-app-badge-contrast-light {
		color: #fff;
	}
	:global([data-theme="light"]) .run-app-badge-contrast-dark {
		color: var(--text);
	}

	.run-app-badge-removed {
		opacity: 0.85;
		color: var(--muted);
		background: color-mix(in srgb, var(--muted) 15%, transparent);
		border-color: color-mix(in srgb, var(--muted) 35%, transparent);
	}
	:global([data-theme="light"]) .run-app-badge-removed {
		color: var(--muted);
		background: color-mix(in srgb, var(--muted) 15%, transparent);
		border-color: color-mix(in srgb, var(--muted) 35%, transparent);
	}
</style>

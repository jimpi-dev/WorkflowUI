<script lang="ts">
	let {
		variant = 'p',
		active = false,
		size = 'sm'
	}: { variant?: 'p' | 'p-plus'; active?: boolean; size?: 'sm' | 'md' } = $props();

	const sizePx = $derived(size === 'sm' ? 18 : 28);
	const rectStyle = $derived(active
		? 'fill: var(--accent-soft, rgba(109, 93, 252, 0.25)); stroke: var(--accent, #6d5dfc);'
		: '');
	const textStyle = $derived(active ? 'fill: var(--accent, #6d5dfc);' : '');
	const plusStroke = $derived(active ? 'var(--accent, #6d5dfc)' : 'currentColor');
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 28 28"
	width={sizePx}
	height={sizePx}
	role="img"
	aria-hidden="true"
	class="preset-icon"
	class:active
	data-active={active}
>
	<rect
		x="1"
		y="1"
		width="26"
		height="26"
		rx="5"
		ry="5"
		fill={active ? 'var(--accent-soft, rgba(109, 93, 252, 0.25))' : 'transparent'}
		stroke={active ? 'var(--accent, #6d5dfc)' : 'currentColor'}
		stroke-width="1.5"
		class="preset-icon-rect"
		style={rectStyle}
	/>
	<text
		x="14"
		y="19"
		text-anchor="middle"
		class="preset-icon-p"
		fill={active ? 'var(--accent, #6d5dfc)' : 'currentColor'}
		stroke="none"
		style={textStyle}
		font-family="Inter, system-ui, sans-serif"
		font-weight="700"
		font-size="14"
	>P</text>
	{#if variant === 'p-plus'}
		<g class="preset-icon-plus" fill="none" stroke={plusStroke} stroke-width="2.5" stroke-linecap="round">
			<line x1="17" y1="7" x2="17" y2="13" />
			<line x1="14" y1="10" x2="20" y2="10" />
		</g>
	{/if}
</svg>

<style>
	.preset-icon {
		display: inline-block;
		flex-shrink: 0;
		color: var(--muted);
		transition: color 0.15s ease, opacity 0.15s ease;
		opacity: 0.9;
	}
	.preset-icon:hover {
		color: var(--text);
		opacity: 1;
	}
	.preset-icon.active {
		color: var(--accent);
		opacity: 1;
	}
	.preset-icon[data-active="true"] .preset-icon-rect {
		fill: var(--accent-soft, rgba(109, 93, 252, 0.25)) !important;
		stroke: var(--accent, #6d5dfc) !important;
	}
	.preset-icon[data-active="true"] .preset-icon-p {
		fill: var(--accent, #6d5dfc) !important;
	}
	.preset-icon[data-active="true"] .preset-icon-plus {
		stroke: var(--accent, #6d5dfc) !important;
	}
</style>

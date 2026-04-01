<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { onMount, onDestroy } from 'svelte';

	interface LogEntry {
		text: string;
		timestamp?: number;
		stream?: 'stdout' | 'stderr';
	}
	
	interface TextSegment {
		text: string;
		class?: string;
	}

	const POLL_INTERVAL_MS = 1500;
	const POLL_INTERVAL_HIDDEN_MS = 5000;
	const DEFAULT_HEIGHT_PX = 240;

	let { open = false, onclose, mobileFullscreen = false } = $props();

	let entries = $state<LogEntry[]>([]);
	let error = $state<string | null>(null);
	let adminOnly = $state(false);
	let loading = $state(true);
	let autoScroll = $state(true);
	let scrollEl: HTMLDivElement | null = $state(null);
	let intervalId: ReturnType<typeof setInterval> | null = null;
	let searchQuery = $state('');
	let clearedAtMs = $state<number | null>(null);
	type HeightMode = 'default' | 'half' | 'full';
	let heightMode = $state<HeightMode>('default');

	const FONT_SIZE_PX = [10, 12, 14, 16, 18];
	const FONT_SIZE_MIN = 0;
	const FONT_SIZE_MAX = FONT_SIZE_PX.length - 1;
	let fontSizeStep = $state(1);

	let consoleFontSizePx = $derived(FONT_SIZE_PX[Math.min(Math.max(fontSizeStep, FONT_SIZE_MIN), FONT_SIZE_MAX)]);

	let consoleBodyHeight = $derived(
		heightMode === 'full' ? '80vh' : heightMode === 'half' ? '50vh' : `${DEFAULT_HEIGHT_PX}px`
	);

	function cycleHeight() {
		heightMode = heightMode === 'default' ? 'half' : heightMode === 'half' ? 'full' : 'default';
	}

	let heightModeTitle = $derived(
		heightMode === 'default'
			? 'Expand to half screen'
			: heightMode === 'half'
				? 'Expand to full'
				: 'Restore default height'
	);

	let filteredEntries = $derived(
		!searchQuery.trim()
			? entries
			: entries.filter((e) => e.text.toLowerCase().includes(searchQuery.trim().toLowerCase()))
	);
	
	function parseAnsiToSegments(raw: string): TextSegment[] {
		const segments: TextSegment[] = [];
		// Match CSI: raw ESC \x1b, or literal \x1b or \u001b (from JSON)
		const ansiRe = /\x1b\[([\d;]*)m|\\x1b\[([\d;]*)m|\\u001b\[([\d;]*)m/g;
		let lastIndex = 0;
		let currentClass: string | undefined;
		let match: RegExpExecArray | null;
		while ((match = ansiRe.exec(raw)) !== null) {
			const code = (match[1] ?? match[2] ?? match[3] ?? '').trim();
			const before = raw.slice(lastIndex, match.index);
			if (before) segments.push({ text: before, class: currentClass });
			lastIndex = match.index + match[0].length;
			if (code === '0' || code === '') {
				currentClass = undefined;
			} else {
				const parts = code.split(';').map((p) => parseInt(p, 10));
				const bold = parts.includes(1);
				if (parts.includes(31)) currentClass = bold ? 'ansi-red-bold' : 'ansi-red';
				else if (parts.includes(33)) currentClass = bold ? 'ansi-yellow-bold' : 'ansi-yellow';
				else if (parts.includes(32)) currentClass = bold ? 'ansi-green-bold' : 'ansi-green';
				else if (parts.includes(36)) currentClass = bold ? 'ansi-cyan-bold' : 'ansi-cyan';
				else if (parts.includes(35)) currentClass = bold ? 'ansi-magenta-bold' : 'ansi-magenta';
				else if (parts.includes(34)) currentClass = bold ? 'ansi-blue-bold' : 'ansi-blue';
				else currentClass = undefined;
			}
		}
		const tail = raw.slice(lastIndex);
		if (tail) segments.push({ text: tail, class: currentClass });
		return segments.length ? segments : [{ text: raw }];
	}

	function textFromItem(item: unknown): string {
		if (typeof item === 'string') return item;
		if (item == null) return '';
		if (typeof item !== 'object') return String(item);
		const o = item as Record<string, unknown>;
		const keys = ['m', 'message', 'text', 'msg', 'line', 'data', 'content', 'output', 'log'];
		for (const k of keys) {
			if (k in o && (typeof o[k] === 'string' || typeof o[k] === 'number')) {
				return String(o[k]);
			}
		}
		// Single string value in object
		const values = Object.values(o).filter((v) => typeof v === 'string' || typeof v === 'number');
		if (values.length === 1) return String(values[0]);
		try {
			return JSON.stringify(o);
		} catch {
			return String(item);
		}
	}

	function normalizeEntries(raw: unknown): LogEntry[] {
		let arr: unknown[] | null = null;
		if (Array.isArray(raw)) {
			arr = raw;
		} else if (raw && typeof raw === 'object') {
			const o = raw as Record<string, unknown>;
			for (const key of ['entries', 'lines', 'logs', 'data']) {
				if (Array.isArray(o[key])) {
					arr = o[key] as unknown[];
					break;
				}
			}
		}
		if (!arr) return [];
		return arr.map((item) => {
			if (typeof item === 'string') return { text: item };
			const o = item && typeof item === 'object' ? (item as Record<string, unknown>) : null;
			if (!o) return { text: String(item) };
			const text = textFromItem(item);
			let timestamp: number | undefined;
			if (typeof o.timestamp === 'number') timestamp = o.timestamp;
			else if (typeof o.time === 'number') timestamp = o.time;
			else if (typeof o.ts === 'number') timestamp = o.ts;
			else if (typeof o.t === 'string') timestamp = Date.parse(o.t);
			else if (typeof o.t === 'number') timestamp = o.t;
			else timestamp = undefined;
			const stream = o.stream === 'stderr' || o.type === 'stderr' ? 'stderr' : 'stdout';
			return { text, timestamp, stream };
		});
	}

	async function fetchLogs() {
		const base = getApiBase() || '';
		try {
			const res = await fetch(`${base}/comfyui/logs/raw`, { signal: AbortSignal.timeout(10000) });
			if (!res.ok) {
				if (res.status === 403) {
					adminOnly = true;
					throw new Error('ComfyUI console is admin-only when authentication is enabled.');
				}
				const data = await res.json().catch(() => ({}));
				const detail = typeof data.detail === 'string' ? data.detail : `Status ${res.status}`;
				throw new Error(detail);
			}
			const data = await res.json();
			let next = normalizeEntries(data);
			if (clearedAtMs != null) {
				next = next.filter((e) => (e.timestamp ?? 0) >= clearedAtMs);
			}
			entries = next;
			error = null;
			adminOnly = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load console';
			entries = [];
		} finally {
			loading = false;
		}
	}

	function startPolling() {
		if (typeof document === 'undefined' || !open) return;
		fetchLogs();
		const isHidden = () => document.visibilityState === 'hidden';
		const ms = () => (isHidden() ? POLL_INTERVAL_HIDDEN_MS : POLL_INTERVAL_MS);
		intervalId = setInterval(fetchLogs, ms());
		document.addEventListener('visibilitychange', onVisibilityChange);
	}

	function onVisibilityChange() {
		if (typeof document === 'undefined' || !intervalId) return;
		clearInterval(intervalId);
		intervalId = setInterval(fetchLogs, document.visibilityState === 'hidden' ? POLL_INTERVAL_HIDDEN_MS : POLL_INTERVAL_MS);
	}

	function stopPolling() {
		if (intervalId) {
			clearInterval(intervalId);
			intervalId = null;
		}
		if (typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', onVisibilityChange);
		}
	}

	function scrollToBottom() {
		if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
	}

	function onScroll() {
		if (!scrollEl) return;
		const { scrollTop, scrollHeight, clientHeight } = scrollEl;
		autoScroll = scrollTop >= scrollHeight - clientHeight - 20;
	}

	$effect(() => {
		if (!open) {
			clearedAtMs = null;
			stopPolling();
			return;
		}
		startPolling();
		return stopPolling;
	});

	$effect(() => {
		if (autoScroll && entries.length > 0 && scrollEl) {
			scrollToBottom();
		}
	});

	onDestroy(stopPolling);

	function clearBuffer() {
		clearedAtMs = Date.now();
		entries = [];
	}
</script>

<div class="console-panel" class:mobile-fullscreen={mobileFullscreen} role="region" aria-label="ComfyUI console output">
	<div class="console-header">
		<span class="console-title">ComfyUI Console</span>
		<div class="console-header-right">
			<div class="console-search-wrap">
				<label class="console-search-label">
					<span class="visually-hidden">Search log</span>
					<input
						type="search"
						class="console-search"
						placeholder="Search…"
						bind:value={searchQuery}
						aria-label="Search console output"
					/>
				</label>
				{#if searchQuery.trim()}
					<button
						type="button"
						class="console-search-clear"
						onclick={() => (searchQuery = '')}
						title="Clear search"
						aria-label="Clear search"
					>
						<svg class="console-search-clear-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
					</button>
				{/if}
			</div>
			<div class="console-font-size" role="group" aria-label="Console text size">
				<button
					type="button"
					class="console-btn console-icon-btn"
					onclick={() => (fontSizeStep = Math.max(FONT_SIZE_MIN, fontSizeStep - 1))}
					title="Decrease text size"
					aria-label="Decrease text size"
					disabled={fontSizeStep <= FONT_SIZE_MIN}
				>
					<svg class="console-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<line x1="5" y1="12" x2="19" y2="12"></line>
					</svg>
				</button>
				<button
					type="button"
					class="console-btn console-icon-btn"
					onclick={() => (fontSizeStep = Math.min(FONT_SIZE_MAX, fontSizeStep + 1))}
					title="Increase text size"
					aria-label="Increase text size"
					disabled={fontSizeStep >= FONT_SIZE_MAX}
				>
					<svg class="console-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<line x1="12" y1="5" x2="12" y2="19"></line>
						<line x1="5" y1="12" x2="19" y2="12"></line>
					</svg>
				</button>
			</div>
			<button
				type="button"
				class="console-btn console-height-btn"
				onclick={cycleHeight}
				title={heightModeTitle}
				aria-label={heightModeTitle}
			>
				<svg class="console-chevron-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					{#if heightMode === 'default'}
						<polyline points="18 15 12 9 6 15"></polyline>
					{:else if heightMode === 'half'}
						<polyline points="18 15 12 9 6 15"></polyline>
					{:else}
						<polyline points="6 9 12 15 18 9"></polyline>
					{/if}
				</svg>
				<span class="console-height-label">{heightMode === 'default' ? 'Default' : heightMode === 'half' ? 'Half' : 'Full'}</span>
			</button>
			<div class="console-actions">
			<button
				type="button"
				class="console-btn"
				onclick={clearBuffer}
				title="Clear"
				aria-label="Clear console"
			>
				Clear
			</button>
			<button
				type="button"
				class="console-btn console-btn-close"
				onclick={() => (onclose ? onclose() : (open = false))}
				title="Close"
				aria-label="Close console"
			>
				Close
			</button>
		</div>
		</div>
	</div>
	<div
		class="console-body"
		style="height: {consoleBodyHeight}; --console-font-size: {consoleFontSizePx}px; --console-ts-size: {Math.max(consoleFontSizePx - 1, 9)}px"
		role="log"
		aria-live="polite"
	>
		{#if loading && entries.length === 0 && !error}
			<div class="console-line console-muted">Loading…</div>
		{:else if error}
			<div class="console-line console-error">
				{#if adminOnly}
					Console unavailable. {error}
				{:else}
					Console unavailable. {error} Ensure ComfyUI is running and supports the logs API (Nov 2024+).
				{/if}
			</div>
		{:else if entries.length === 0}
			<div class="console-line console-muted">No log output yet.</div>
		{:else}
			<div
				class="console-scroll"
				bind:this={scrollEl}
				onscroll={onScroll}
			>
				{#if filteredEntries.length === 0}
					<div class="console-line console-muted">No matching lines.{#if searchQuery.trim()} Try a different search.{/if}</div>
				{:else}
					{#each filteredEntries as entry, i (i)}
						<div
							class="console-line"
							class:console-line-stderr={entry.stream === 'stderr'}
						>
							{#if entry.timestamp != null}
								<span class="console-ts" aria-hidden="true">{new Date(entry.timestamp).toISOString().slice(11, 23)}</span>
							{/if}
							<span class="console-text">
								{#each parseAnsiToSegments(entry.text) as seg}
									{#if seg.class}
										<span class={seg.class}>{seg.text}</span>
									{:else}
										{seg.text}
									{/if}
								{/each}
							</span>
						</div>
					{/each}
				{/if}
			</div>
		{/if}
	</div>
</div>

<style>
	.console-panel {
		background: var(--console-bg);
		border-top: 1px solid var(--console-border);
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
	}
	.console-panel.mobile-fullscreen {
		height: 100dvh;
		border-radius: 0;
		border-top: none;
	}
	.console-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.35rem 0.75rem;
		min-height: 32px;
		border-bottom: 1px solid var(--console-border);
		background: color-mix(in srgb, var(--console-bg) 98%, var(--text));
	}
	.console-title {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--console-text);
		flex-shrink: 0;
	}
	.console-header-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.console-search-wrap {
		display: flex;
		align-items: center;
		min-width: 0;
		gap: 0;
		position: relative;
	}
	.console-search-label {
		display: flex;
		min-width: 0;
	}
	.console-search {
		width: 100%;
		min-width: 120px;
		max-width: 200px;
		padding: 0.2rem 0.5rem;
		padding-right: 1.6rem;
		font-size: 0.75rem;
		border: 1px solid var(--console-border);
		border-radius: 6px;
		background: var(--console-bg);
		color: var(--console-text);
	}
	.console-search-wrap:has(.console-search-clear) .console-search {
		padding-right: 1.75rem;
	}
	.console-search::placeholder {
		color: var(--console-muted);
	}
	.console-search:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.console-search-clear {
		position: absolute;
		right: 0.25rem;
		top: 50%;
		transform: translateY(-50%);
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		padding: 0;
		border: none;
		border-radius: 4px;
		background: transparent;
		color: var(--console-muted);
		cursor: pointer;
	}
	.console-search-clear:hover {
		color: var(--console-text);
		background: color-mix(in srgb, var(--console-text) 15%, transparent);
	}
	.console-search-clear-icon {
		width: 12px;
		height: 12px;
	}
	.console-font-size {
		display: inline-flex;
		align-items: center;
		gap: 0;
	}
	.console-icon-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		padding: 0;
	}
	.console-icon-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.console-icon-sm {
		width: 14px;
		height: 14px;
	}
	.console-height-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.console-chevron-icon {
		width: 14px;
		height: 14px;
		flex-shrink: 0;
	}
	.console-height-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: var(--console-muted);
	}
	.console-height-btn:hover .console-height-label {
		color: var(--console-text);
	}
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
	.console-actions {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}
	.console-btn {
		font-size: 0.75rem;
		padding: 0.2rem 0.5rem;
		border-radius: 6px;
		border: 1px solid var(--console-border);
		background: transparent;
		color: var(--console-muted);
		cursor: pointer;
	}
	.console-btn:hover {
		color: var(--console-text);
		background: color-mix(in srgb, var(--console-text) 10%, transparent);
	}
	.console-btn-close {
		color: var(--console-text);
	}
	.console-body {
		overflow: hidden;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.console-panel.mobile-fullscreen .console-body {
		height: auto !important;
		flex: 1;
	}
	.console-scroll {
		overflow-y: auto;
		flex: 1;
		padding: 0.5rem 0.75rem;
		font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', Monaco, Consolas, monospace;
		font-size: var(--console-font-size, 12px);
		line-height: 1.4;
		color: var(--console-text);
		white-space: pre-wrap;
		word-break: break-all;
	}
	.console-line {
		display: block;
		margin: 0;
		padding: 0.1rem 0;
	}
	.console-line-stderr {
		color: var(--console-error);
	}
	.console-ts {
		display: inline-block;
		min-width: 10ch;
		margin-right: 0.5rem;
		color: var(--console-muted);
		font-size: var(--console-ts-size, 11px);
	}
	.console-text {
		white-space: pre-wrap;
		word-break: break-all;
	}
	.console-muted {
		color: var(--console-muted);
		font-style: italic;
	}
	.console-error {
		color: var(--console-error);
	}

	/* ANSI color segments (ComfyUI may embed these in messages) */
	.ansi-red { color: #f85149; }
	.ansi-red-bold { color: #ff7b72; font-weight: 600; }
	.ansi-yellow { color: #d29922; }
	.ansi-yellow-bold { color: #e3b341; font-weight: 600; }
	.ansi-green { color: #3fb950; }
	.ansi-green-bold { color: #56d364; font-weight: 600; }
	.ansi-cyan { color: #39c5cf; }
	.ansi-cyan-bold { color: #56d4dd; font-weight: 600; }
	.ansi-magenta { color: #bc8cff; }
	.ansi-magenta-bold { color: #d2a8ff; font-weight: 600; }
	.ansi-blue { color: #58a6ff; }
	.ansi-blue-bold { color: #79c0ff; font-weight: 600; }
</style>

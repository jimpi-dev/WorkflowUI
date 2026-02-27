<script lang="ts">
	import '$lib/styles/home.css';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import type { BlogPost } from '$lib/blog';
	import { NODE_SPECS } from '$lib/workflow/nodes';

	type PostWithHtml = BlogPost & { html: string };

	/** Sorted list of supported ComfyUI node class names (for home page lookup). */
	const SUPPORTED_NODE_CLASSES = Object.keys(NODE_SPECS).sort();

	// No server load: avoid fetching /__data.json when navigating to / (backend serves static and would return index.html).
	let { data = { blogPosts: [] } }: { data: { blogPosts: BlogPost[] } } = $props();
	let blogPosts = $state<PostWithHtml[]>([]);
	/** Set of post keys (slug+date) that are expanded; all expanded by default */
	let expandedKeys = $state<Set<string>>(new Set());

	/** Search filter for supported node classes (home page). */
	let nodeClassSearch = $state('');
	let filteredNodeClasses = $derived(
		nodeClassSearch.trim() === ''
			? SUPPORTED_NODE_CLASSES
			: SUPPORTED_NODE_CLASSES.filter((name) =>
					name.toLowerCase().includes(nodeClassSearch.trim().toLowerCase())
				)
	);

	let showNotSupportedHint = $derived(
		nodeClassSearch.trim() !== '' && filteredNodeClasses.length === 0
	);

	const GITHUB_ISSUES_URL = 'https://github.com/WorkflowUI/WorkflowUI/issues';

	onMount(async () => {
		try {
			const [{ getBlogPosts }, { lexer, parser }] = await Promise.all([
				import('$lib/blog'),
				import('marked')
			]);
			const raw = getBlogPosts();
			// Use lexer + parser for sync rendering (avoids marked() async/throw issues in v17)
			const render = (content: string): string => {
				try {
					const tokens = lexer(content);
					return parser(tokens) ?? '';
				} catch (e) {
					console.error('Markdown render error:', e);
					return '<p>Failed to render content.</p>';
				}
			};
			blogPosts = raw.map((post) => ({ ...post, html: render(post.content) }));
			// Auto-expand all posts
			expandedKeys = new Set(blogPosts.map((p) => p.slug + p.date));
		} catch (e) {
			console.error('Blog load failed:', e);
		}
	});

	function toggleExpanded(key: string) {
		const next = new Set(expandedKeys);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		expandedKeys = next;
	}

	/** Derive title from first # heading or slug */
	function getTitle(content: string, slug: string): string {
		const match = content.match(/^#\s+(.+)$/m);
		return match ? match[1].trim() : slug.replace(/-/g, ' ');
	}
</script>

<div class="landing">
	<h1>WorkflowUI</h1>
	<p>Turn ComfyUI workflows into web apps.</p>
	<p class="landing-intro">
		Import a ComfyUI workflow, then manage it from <strong>Apps</strong> or <strong>Projects</strong>.
		Scroll down for <strong>updates and tips</strong> — we post hints and how-tos there.
	</p>

	<div class="landing-actions">
		<button onclick={() => goto('/import')}>Import a workflow</button>
		<button onclick={() => goto('/apps')}>Go to Apps</button>
		<button onclick={() => goto('/projects')}>Go to Projects</button>
	</div>
</div>

<div class="home-content">
	<div class="home-col home-col-blog">
		{#if blogPosts.length > 0}
			<section class="blog-section" aria-label="Blog and updates">
				<h2 class="blog-section-title">Updates &amp; notes</h2>
				<ul class="blog-list">
					{#each blogPosts as post (post.slug + post.date)}
						<li class="blog-card">
							<button
								type="button"
								class="blog-card-header"
								onclick={() => toggleExpanded(post.slug + post.date)}
								aria-expanded={expandedKeys.has(post.slug + post.date)}
							>
								<span class="blog-card-date">{post.date}</span>
								<span class="blog-card-title">{getTitle(post.content, post.slug)}</span>
							</button>
							{#if expandedKeys.has(post.slug + post.date)}
								<div class="blog-card-body prose">
									{@html post.html}
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{:else}
			<section class="blog-section blog-section-empty" aria-label="Blog and updates">
				<h2 class="blog-section-title">Updates &amp; notes</h2>
			</section>
		{/if}
	</div>

	<div class="home-col home-col-nodes">
		<section class="node-classes-section" aria-label="Supported node classes">
			<div class="node-classes-header">
				<h2 class="node-classes-title">Supported node classes</h2>
				<span class="node-classes-badge">{SUPPORTED_NODE_CLASSES.length}</span>
			</div>
			<p class="node-classes-desc">
				ComfyUI node types WorkflowUI can render in app forms. Search to check support.
			</p>
			<div class="node-classes-search-wrap">
				<label for="node-class-search" class="node-classes-search-label">Search</label>
				<input
					id="node-class-search"
					type="search"
					class="node-classes-search"
					placeholder="e.g. KSampler, LoadImage…"
					aria-describedby="node-class-search-hint"
					bind:value={nodeClassSearch}
				/>
				<span id="node-class-search-hint" class="node-classes-search-hint" aria-live="polite">
			{#if showNotSupportedHint}
				The node class <code>{nodeClassSearch.trim()}</code> is not yet supported. Request it via
				<a href={GITHUB_ISSUES_URL} target="_blank" rel="noopener noreferrer">GitHub issues</a>.
			{:else if nodeClassSearch.trim() !== ''}
				{filteredNodeClasses.length} match{filteredNodeClasses.length === 1 ? '' : 'es'}
			{:else}
				All {SUPPORTED_NODE_CLASSES.length} supported
			{/if}
				</span>
			</div>
			{#if showNotSupportedHint}
		<div class="node-classes-not-found-card">
			<p class="node-classes-not-found">
			No supported node class matches “<strong>{nodeClassSearch.trim()}</strong>”. Request support via
			<a href={GITHUB_ISSUES_URL} target="_blank" rel="noopener noreferrer">GitHub issues</a>.
			</p>
		</div>
			{:else}
				<div class="node-classes-list-wrap">
					<ul class="node-classes-list">
						{#each filteredNodeClasses as name (name)}
							<li class="node-classes-item"><code>{name}</code></li>
						{/each}
					</ul>
				</div>
			{/if}
		</section>
	</div>
</div>

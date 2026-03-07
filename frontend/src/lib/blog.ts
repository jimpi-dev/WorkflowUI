const blogModules = import.meta.glob<{ default: string }>('../blog/*.md', {
	query: '?raw',
	import: 'default',
	eager: true
});

const assetModules = import.meta.glob<{ default: string }>('../blog/assets/*', {
	query: '?url',
	import: 'default',
	eager: true
});

const BLOG_FILENAME_RE = /^(\d{4}-\d{2}-\d{2})_(.+)\.md$/;

const assetUrlByFilename: Record<string, string> = {};
for (const [path, url] of Object.entries(assetModules)) {
	const filename = path.split('/').pop() ?? '';
	const resolved = typeof url === 'string' ? url : (url as { default?: string })?.default;
	if (filename && typeof resolved === 'string') assetUrlByFilename[filename] = resolved;
}

function rewriteAssetPaths(content: string): string {
	let out = content;
	for (const [filename, url] of Object.entries(assetUrlByFilename)) {
		out = out.replaceAll(`assets/${filename}`, url);
	}
	return out;
}

export type BlogPost = { date: string; slug: string; content: string };

export function getBlogPosts(): BlogPost[] {
	const posts: BlogPost[] = [];
	for (const [path, raw] of Object.entries(blogModules)) {
		const filename = path.split('/').pop() ?? '';
		const match = filename.match(BLOG_FILENAME_RE);
		let content = typeof raw === 'string' ? raw : (raw as { default?: string })?.default;
		if (!match || typeof content !== 'string') continue;
		content = rewriteAssetPaths(content);
		const [, date, slug] = match;
		posts.push({ date, slug: slug.replace(/\.md$/, ''), content });
	}
	posts.sort((a, b) => b.date.localeCompare(a.date));
	return posts;
}

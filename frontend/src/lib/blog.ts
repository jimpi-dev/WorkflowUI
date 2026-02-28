const blogModules = import.meta.glob<{ default: string }>('../blog/*.md', {
	query: '?raw',
	import: 'default',
	eager: true
});

const BLOG_FILENAME_RE = /^(\d{4}-\d{2}-\d{2})_(.+)\.md$/;

export type BlogPost = { date: string; slug: string; content: string };

export function getBlogPosts(): BlogPost[] {
	const posts: BlogPost[] = [];
	for (const [path, raw] of Object.entries(blogModules)) {
		const filename = path.split('/').pop() ?? '';
		const match = filename.match(BLOG_FILENAME_RE);
		const content = typeof raw === 'string' ? raw : (raw as { default?: string })?.default;
		if (!match || typeof content !== 'string') continue;
		const [, date, slug] = match;
		posts.push({ date, slug: slug.replace(/\.md$/, ''), content });
	}
	posts.sort((a, b) => b.date.localeCompare(a.date));
	return posts;
}

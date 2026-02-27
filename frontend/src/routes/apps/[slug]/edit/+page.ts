import { getApiBase } from '$lib/config';

export async function load({ params, fetch }) {
	const apiBase = getApiBase() || '';
	try {
		const res = await fetch(`${apiBase}/app/${params.slug}`);
		if (!res.ok) return { appData: null, slug: params.slug };
		const appData = await res.json();
		return { appData, slug: params.slug };
	} catch {
		return { appData: null, slug: params.slug };
	}
}

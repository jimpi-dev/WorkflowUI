import { getApiBase } from '$lib/config';

export async function load({ url, fetch }) {
	let versionId: string | null = null;
	try {
		versionId = url.searchParams.get('versionId');
	} catch {
	}
	if (!versionId) {
		return { version: null, versionId: null };
	}
	const apiBase = getApiBase() || '';
	try {
		const res = await fetch(`${apiBase}/workflow-versions/${versionId}`);
		if (!res.ok) return { version: null, versionId };
		const version = await res.json();
		return { version, versionId };
	} catch {
		return { version: null, versionId };
	}
}

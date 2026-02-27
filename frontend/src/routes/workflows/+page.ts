import { getApiBase } from '$lib/config';

export async function load({ fetch }) {
	const apiBase = getApiBase() || '';
	let definitions: { id: string; name: string; created_at: number; created_from_image_import?: boolean }[] = [];
	try {
		const res = await fetch(`${apiBase}/workflow-definitions`);
		if (res.ok) definitions = await res.json();
	} catch {
		// ignore
	}
	return { definitions };
}

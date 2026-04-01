import type { HandleFetch } from '@sveltejs/kit';
import { appConfig } from '$lib/config';

function isApiRequest(url: URL): boolean {
	if (url.pathname.startsWith('/api/')) return true;
	if (url.pathname === '/api') return true;
	const configured = (appConfig.backendUrl || '').trim();
	if (!configured) return false;
	try {
		const backendUrl = new URL(configured, window.location.origin);
		return url.origin === backendUrl.origin;
	} catch {
		return false;
	}
}

export const handleFetch: HandleFetch = async ({ request, fetch }) => {
	try {
		const targetUrl = new URL(request.url, window.location.origin);
		if (!isApiRequest(targetUrl) || request.credentials === 'include') {
			return fetch(request);
		}
		return fetch(new Request(request, { credentials: 'include' }));
	} catch {
		return fetch(request);
	}
};

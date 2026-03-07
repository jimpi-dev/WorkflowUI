import { getApiBase } from '$lib/config';

function baseUrl(): string {
    return getApiBase().replace(/\/$/, '');
}

function url(path: string): string {
    const p = path.startsWith('/') ? path.slice(1) : path;
    const base = baseUrl();
    return base ? `${base}/${p}` : `/${p}`;
}

export const api = {
    get(path: string, init?: RequestInit): Promise<Response> {
        return fetch(url(path), { ...init, cache: 'no-store' });
    },
    post(path: string, body: object, init?: RequestInit): Promise<Response> {
        return fetch(url(path), {
            ...init,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string>) },
            body: JSON.stringify(body)
        });
    },
    delete(path: string, init?: RequestInit): Promise<Response> {
        return fetch(url(path), { ...init, method: 'DELETE' });
    }
};

const APP_READY_POLL_MS = 350;
const APP_READY_MAX_WAIT_MS = 4000;

export async function waitForAppToBeAvailable(slug: string): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < APP_READY_MAX_WAIT_MS) {
        const res = await api.get(`app/${slug}`);
        if (res.ok) return;
        await new Promise((r) => setTimeout(r, APP_READY_POLL_MS));
    }
}

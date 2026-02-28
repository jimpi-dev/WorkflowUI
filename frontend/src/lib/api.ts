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

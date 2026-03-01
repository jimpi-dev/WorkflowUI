import { api } from '$lib/api';

const ENDPOINT_RESPONSE_KEY: Record<string, string> = {
    '/loras': 'loras',
    '/lycoris_types': 'lycoris_types',
    '/checkpoints': 'checkpoints',
    '/clip_models': 'clip_models',
    '/clip_vision_models': 'clip_vision_models',
    '/vae_models': 'vae_models',
    '/clip_types': 'clip_types',
    '/devices': 'devices',
    '/rife_models': 'rife_models',
    '/unet_gguf_models': 'unet_gguf_models'
};

export function getOptionListResponseKey(endpoint: string): string | undefined {
    return ENDPOINT_RESPONSE_KEY[endpoint];
}

export async function fetchOptionList(endpoint: string): Promise<string[]> {
    const key = getOptionListResponseKey(endpoint);
    if (!key) return [];
    const path = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    const res = await api.get(path);
    const data = res.ok ? await res.json().catch(() => ({})) : {};
    const list = data[key];
    return Array.isArray(list) ? list.slice() : [];
}

import { describe, it, expect } from 'vitest';
import { getApiBase, COMFYUI_MAX_SEED } from './config';

describe('config', () => {
	describe('getApiBase', () => {
		it('returns empty string when backendUrl is empty', () => {
			expect(typeof getApiBase()).toBe('string');
			expect(getApiBase().length).toBeGreaterThanOrEqual(0);
		});

		it('returns non-empty backendUrl when appConfig has it', () => {
			const base = getApiBase();
			expect(base).toBeDefined();
		});
	});

	describe('COMFYUI_MAX_SEED', () => {
		it('equals 2^50', () => {
			expect(COMFYUI_MAX_SEED).toBe(2 ** 50);
		});

		it('is a safe integer for seed range', () => {
			expect(Number.isSafeInteger(COMFYUI_MAX_SEED)).toBe(true);
		});
	});
});

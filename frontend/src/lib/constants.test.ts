import { describe, it, expect } from 'vitest';
import { QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME } from './constants';

describe('constants', () => {
	describe('QUICK_RUNS_PROJECT_ID', () => {
		it('is the fixed quick runs UUID', () => {
			expect(QUICK_RUNS_PROJECT_ID).toBe('00000000-0000-0000-0000-000000000002');
		});

		it('is a valid UUID format', () => {
			const uuidRe =
				/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
			expect(QUICK_RUNS_PROJECT_ID).toMatch(uuidRe);
		});
	});

	describe('QUICK_RUNS_PROJECT_NAME', () => {
		it('is the display name for quick runs', () => {
			expect(QUICK_RUNS_PROJECT_NAME).toBe('Quick runs');
		});

		it('is a non-empty string', () => {
			expect(QUICK_RUNS_PROJECT_NAME.length).toBeGreaterThan(0);
		});
	});
});

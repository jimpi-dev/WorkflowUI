import { describe, it, expect } from 'vitest';
import { getContrastForeground, gradientEndColor } from './color';

describe('color', () => {
	describe('getContrastForeground', () => {
		it('returns "dark" for light backgrounds (high luminance)', () => {
			expect(getContrastForeground('#ffffff')).toBe('dark');
			expect(getContrastForeground('#fff')).toBe('dark');
			expect(getContrastForeground('#eeeeee')).toBe('dark');
			expect(getContrastForeground('#e4e4e4')).toBe('dark');
		});

		it('returns "light" for dark backgrounds (low luminance)', () => {
			expect(getContrastForeground('#000000')).toBe('light');
			expect(getContrastForeground('#000')).toBe('light');
			expect(getContrastForeground('#111')).toBe('light');
			expect(getContrastForeground('#333333')).toBe('light');
			expect(getContrastForeground('#666666')).toBe('light');
		});

		it('uses 0.4 luminance threshold (boundary)', () => {
			expect(getContrastForeground('#888888')).toBe('light');
			expect(getContrastForeground('#777777')).toBe('light');
		});

		it('accepts hex with or without leading #', () => {
			expect(getContrastForeground('ffffff')).toBe('dark');
			expect(getContrastForeground('#ffffff')).toBe('dark');
		});
	});

	describe('gradientEndColor', () => {
		it('returns the same hex string (caller uses CSS for gradient)', () => {
			expect(gradientEndColor('#ff5500')).toBe('#ff5500');
			expect(gradientEndColor('#abc')).toBe('#abc');
			expect(gradientEndColor('123456')).toBe('123456');
		});
	});
});

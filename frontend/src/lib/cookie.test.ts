import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	getCookie,
	setCookie,
	THUMB_SIZE_COOKIE,
	getThumbSizeCookie,
	setThumbSizeCookie,
	NOTES_COLLAPSED_COOKIE,
	getNotesCollapsedCookie,
	setNotesCollapsedCookie
} from './cookie';

describe('cookie', () => {
	let cookieStore: string;

	beforeEach(() => {
		cookieStore = '';
		vi.stubGlobal('document', {
			get cookie() {
				return cookieStore;
			},
			set cookie(val: string) {
				const part = val.split(';')[0].trim();
				const name = part.split('=')[0];
				const newPairs = cookieStore
					.split(';')
					.map((p) => p.trim())
					.filter((p) => p && !p.startsWith(name + '='));
				newPairs.push(part);
				cookieStore = newPairs.join('; ');
			}
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	describe('getCookie', () => {
		it('returns null when cookie is not set', () => {
			expect(getCookie('missing')).toBeNull();
		});

		it('returns value when cookie is set', () => {
			document.cookie = 'foo=bar';
			expect(getCookie('foo')).toBe('bar');
		});

		it('returns first value when multiple cookies exist', () => {
			document.cookie = 'a=1';
			document.cookie = 'b=2';
			expect(getCookie('a')).toBe('1');
			expect(getCookie('b')).toBe('2');
		});

		it('decodes URI-encoded value', () => {
			document.cookie = 'key=' + encodeURIComponent('hello world');
			expect(getCookie('key')).toBe('hello world');
		});
	});

	describe('setCookie', () => {
		it('sets cookie with name and value', () => {
			setCookie('test', 'value');
			expect(getCookie('test')).toBe('value');
		});

		it('encodes value', () => {
			setCookie('x', 'a=b; c');
			expect(document.cookie).toContain('x=');
		});
	});

	describe('getThumbSizeCookie / setThumbSizeCookie', () => {
		it('returns medium when not set', () => {
			expect(getThumbSizeCookie()).toBe('medium');
		});

		it('returns saved size when set', () => {
			setThumbSizeCookie('small');
			expect(getThumbSizeCookie()).toBe('small');
			setThumbSizeCookie('large');
			expect(getThumbSizeCookie()).toBe('large');
		});

		it('returns medium for invalid stored value', () => {
			setCookie(THUMB_SIZE_COOKIE, 'invalid');
			expect(getThumbSizeCookie()).toBe('medium');
		});
	});

	describe('getNotesCollapsedCookie / setNotesCollapsedCookie', () => {
		it('returns false when not set', () => {
			expect(getNotesCollapsedCookie()).toBe(false);
		});

		it('returns true when set to 1 or true', () => {
			setNotesCollapsedCookie(true);
			expect(getNotesCollapsedCookie()).toBe(true);
			setCookie(NOTES_COLLAPSED_COOKIE, 'true');
			expect(getNotesCollapsedCookie()).toBe(true);
		});

		it('returns false when set to 0', () => {
			setNotesCollapsedCookie(false);
			expect(getNotesCollapsedCookie()).toBe(false);
		});
	});
});

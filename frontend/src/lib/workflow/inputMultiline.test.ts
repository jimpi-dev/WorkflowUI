import { describe, it, expect } from 'vitest';
import { effectiveTextMultiline } from './inputMultiline';

describe('effectiveTextMultiline', () => {
	it('respects explicit API false', () => {
		expect(
			effectiveTextMultiline({
				type: 'text',
				field: 'text',
				classType: 'CLIPTextEncode',
				multiline: false
			})
		).toBe(false);
	});

	it('uses NODE_SPECS when API omits multiline (legacy DB)', () => {
		expect(
			effectiveTextMultiline({
				type: 'text',
				field: 'text',
				classType: 'CLIPTextEncode',
				multiline: undefined
			})
		).toBe(true);
	});

	it('treats custom *prompt* field names as multiline when spec unknown', () => {
		expect(
			effectiveTextMultiline({
				type: 'text',
				field: '12.positive_prompt',
				classType: 'WanSomeNode',
				multiline: undefined
			})
		).toBe(true);
	});
});

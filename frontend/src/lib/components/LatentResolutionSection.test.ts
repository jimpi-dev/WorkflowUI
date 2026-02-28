import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import LatentResolutionSection from './LatentResolutionSection.svelte';

describe('LatentResolutionSection', () => {
	it('renders width and height inputs with data-binding-key so dimensions are read from DOM at submit', () => {
		const groupInputs = [
			{
				key: '18.width_override',
				label: 'Width',
				type: 'number' as const,
				field: 'width_override',
				nodeId: '18',
				classType: 'SDXLEmptyLatentSizePicker+',
				default: 1024,
				min: 64,
				max: 2048,
				step: 8
			},
			{
				key: '18.height_override',
				label: 'Height',
				type: 'number' as const,
				field: 'height_override',
				nodeId: '18',
				classType: 'SDXLEmptyLatentSizePicker+',
				default: 1024,
				min: 64,
				max: 2048,
				step: 8
			}
		];
		const values = { '18.width_override': 512, '18.height_override': 512 };

		const { container } = render(LatentResolutionSection, {
			props: { groupInputs, values }
		});

		const widthWrap = container.querySelector('[data-binding-key="18.width_override"]');
		const heightWrap = container.querySelector('[data-binding-key="18.height_override"]');

		expect(widthWrap).toBeTruthy();
		expect(heightWrap).toBeTruthy();
		expect(widthWrap?.querySelector('input[type="number"]')).toBeTruthy();
		expect(heightWrap?.querySelector('input[type="number"]')).toBeTruthy();
	});
});

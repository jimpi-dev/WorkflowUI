import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import LoRASection from './LoRASection.svelte';

function mockGroupInputs() {
	return [
		{ key: '162.lora_5.on', label: 'On', type: 'boolean' as const, field: 'lora_5.on', nodeId: '162', classType: 'Power Lora Loader (rgthree)' },
		{ key: '162.lora_5.lora', label: 'LoRA', type: 'select' as const, field: 'lora_5.lora', nodeId: '162', classType: 'Power Lora Loader (rgthree)' },
		{ key: '162.lora_5.strength', label: 'Strength', type: 'number' as const, field: 'lora_5.strength', nodeId: '162', classType: 'Power Lora Loader (rgthree)', min: 0, max: 2, step: 0.05 }
	];
}

describe('LoRASection', () => {
	it('renders hidden input with data-binding-key so selected LoRA is read from DOM at submit', () => {
		const groupInputs = mockGroupInputs();
		const values = { '162.lora_5.on': true, '162.lora_5.lora': 'SomeLora.safetensors', '162.lora_5.strength': 0.85 };

		const { container } = render(LoRASection, {
			props: { groupInputs, values, canEditLoras: true, availableLoras: [], workflowLoraPaths: [] }
		});

		const hidden = container.querySelector('input[type="hidden"][data-binding-key="162.lora_5.lora"]');
		expect(hidden).toBeTruthy();
		expect((hidden as HTMLInputElement).value).toBe('SomeLora.safetensors');
	});

	it('hidden input has initial value from values so buildRunValues can read current selection from DOM', () => {
		const groupInputs = mockGroupInputs();
		const values = { '162.lora_5.on': true, '162.lora_5.lora': 'PickedLora.safetensors', '162.lora_5.strength': 0.9 };

		const { container } = render(LoRASection, {
			props: { groupInputs, values, canEditLoras: true, availableLoras: [], workflowLoraPaths: [] }
		});

		const hidden = container.querySelector('input[type="hidden"][data-binding-key="162.lora_5.lora"]') as HTMLInputElement;
		expect(hidden).toBeTruthy();
		expect(hidden.value).toBe('PickedLora.safetensors');
	});
});

import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import SeedInput from './SeedInput.svelte';

describe('SeedInput', () => {
	const defaultInput = {
		key: '9.seed',
		label: 'Seed',
		role: 'seed' as const,
		parent: 'KSampler',
		type: 'seed' as const,
		nodeId: '9',
		field: 'seed',
		classType: 'KSampler'
	};

	it('renders label and number input with initial value', () => {
		const value = 12345;
		const { getByText, getByRole } = render(SeedInput, {
			props: { input: defaultInput, value }
		});

		expect(getByText('Seed')).toBeInTheDocument();
		const numberInput = getByRole('spinbutton');
		expect(numberInput).toHaveValue(12345);
	});

	it('shows "Random seed" hint when value is 0', () => {
		const { getByText } = render(SeedInput, {
			props: { input: defaultInput, value: 0 }
		});

		expect(getByText('Random seed')).toBeInTheDocument();
	});

	it('randomize button updates the displayed value', async () => {
		const value = 999;
		const { getByRole } = render(SeedInput, {
			props: { input: defaultInput, value }
		});

		const randomizeBtn = getByRole('button', { name: /randomize seed/i });
		const numberInput = getByRole('spinbutton');
		expect(numberInput).toHaveValue(999);

		await fireEvent.click(randomizeBtn);

		const newVal = (numberInput as HTMLInputElement).valueAsNumber;
		expect(newVal).toBeGreaterThanOrEqual(0);
		expect(Number.isInteger(newVal)).toBe(true);
	});

	it('randomize button calls onValueChange so parent can sync (sampler section seed button)', async () => {
		const value = 0;
		const onValueChange = vi.fn();
		const { getByRole } = render(SeedInput, {
			props: { input: defaultInput, value, onValueChange }
		});

		const randomizeBtn = getByRole('button', { name: /randomize seed/i });
		await fireEvent.click(randomizeBtn);

		expect(onValueChange).toHaveBeenCalledTimes(1);
		const newSeed = onValueChange.mock.calls[0][0];
		expect(typeof newSeed).toBe('number');
		expect(Number.isInteger(newSeed)).toBe(true);
		expect(newSeed).toBeGreaterThanOrEqual(0);
	});

	it('increment button increases value and updates displayed input', async () => {
		const value = 10;
		const { getByRole } = render(SeedInput, {
			props: { input: defaultInput, value }
		});

		const incrementBtn = getByRole('button', { name: /increment seed/i });
		const numberInput = getByRole('spinbutton');
		expect(numberInput).toHaveValue(10);

		await fireEvent.click(incrementBtn);
		expect(numberInput).toHaveValue(11);
	});

	it('increment and decrement call onValueChange so parent stays in sync', async () => {
		const onValueChange = vi.fn();
		const { getByRole } = render(SeedInput, {
			props: { input: defaultInput, value: 5, onValueChange }
		});

		await fireEvent.click(getByRole('button', { name: /increment seed/i }));
		expect(onValueChange).toHaveBeenLastCalledWith(6);

		await fireEvent.click(getByRole('button', { name: /decrement seed/i }));
		expect(onValueChange).toHaveBeenLastCalledWith(5);
	});

	it('decrement button decreases value but not below 0', async () => {
		const value = 1;
		const { getByRole } = render(SeedInput, {
			props: { input: defaultInput, value }
		});

		const decrementBtn = getByRole('button', { name: /decrement seed/i });
		const numberInput = getByRole('spinbutton');
		expect(numberInput).toHaveValue(1);

		await fireEvent.click(decrementBtn);
		expect(numberInput).toHaveValue(0);

		await fireEvent.click(decrementBtn);
		expect(numberInput).toHaveValue(0);
	});
});

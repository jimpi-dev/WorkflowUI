import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import RunParamGroup from './RunParamGroup.svelte';

describe('RunParamGroup', () => {
	it('shows current runs value in number input', () => {
		const values = { runs: 5 };
		const { getByRole } = render(RunParamGroup, {
			props: {
				values,
				formId: 'test-form',
				onQueueClick: vi.fn(),
				onRandomClick: vi.fn()
			}
		});

		const numberInput = getByRole('spinbutton');
		expect(numberInput).toHaveValue(5);
	});

	it('updates values when number input changes', async () => {
		const values = { runs: 1 };
		const { getByRole } = render(RunParamGroup, {
			props: {
				values,
				formId: 'test-form',
				onQueueClick: vi.fn(),
				onRandomClick: vi.fn()
			}
		});

		const numberInput = getByRole('spinbutton');
		await fireEvent.input(numberInput, { target: { value: '10' } });

		expect(values.runs).toBe(10);
	});

	it('renders action buttons when showActions is true', () => {
		const { getByRole } = render(RunParamGroup, {
			props: {
				values: { runs: 2 },
				formId: 'test-form',
				onQueueClick: vi.fn(),
				onRandomClick: vi.fn(),
				showActions: true
			}
		});

		expect(getByRole('button', { name: /queue for generation/i })).toBeInTheDocument();
		expect(getByRole('button', { name: /random seed/i })).toBeInTheDocument();
	});

	it('hides action buttons when showActions is false', () => {
		const { queryByRole } = render(RunParamGroup, {
			props: {
				values: { runs: 2 },
				formId: 'test-form',
				onQueueClick: vi.fn(),
				onRandomClick: vi.fn(),
				showActions: false
			}
		});

		expect(queryByRole('button', { name: /queue for generation/i })).toBeNull();
		expect(queryByRole('button', { name: /random seed/i })).toBeNull();
	});
});

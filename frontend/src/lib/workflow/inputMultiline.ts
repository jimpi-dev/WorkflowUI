import { NODE_SPECS } from '$lib/workflow/nodes';
import type { NodeSpec, WorkflowInput } from '$lib/workflow/types';

/** Field names that are almost always long prompt text (legacy rows without `multiline` in DB). */
const LEGACY_PROMPT_FIELD =
	/^(text|value|prompt|positive|negative|positive_prompt|negative_prompt|tags|lyrics)$/i;

function fieldTail(field: string | undefined): string {
	if (!field) return '';
	const parts = field.split('.');
	return parts[parts.length - 1] ?? field;
}

/**
 * App builder: whether the default-value editor should use a textarea.
 * Stored `detected_inputs` from older imports often omit `multiline`; this merges the API flag,
 * frontend NODE_SPECS, and safe field-name heuristics (e.g. Wan / custom nodes).
 */
export function effectiveTextMultiline(input: Pick<WorkflowInput, 'type' | 'field' | 'classType' | 'multiline'>): boolean {
	if (input.multiline === false) return false;
	if (input.multiline === true) return true;
	if (input.type !== 'text') return false;

	const tail = fieldTail(input.field);
	const specs = NODE_SPECS as Record<string, NodeSpec>;
	const spec = input.classType ? specs[input.classType] : undefined;
	const fixed = spec?.fixedInputs?.[tail];
	if (fixed && typeof fixed === 'object' && 'multiline' in fixed) {
		return fixed.multiline === true;
	}

	if (LEGACY_PROMPT_FIELD.test(tail)) return true;
	if (/^input_text_\d+$/.test(tail)) return true;
	// Custom nodes (e.g. Wan I2V) often use *prompt* in the widget name without being in NODE_SPECS.
	if (tail.toLowerCase().includes('prompt')) return true;

	return false;
}

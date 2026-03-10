import type { WorkflowModel, WorkflowBinding } from '$lib/workflow/types';

const DIMENSION_FIELDS = new Set([
    'width',
    'height',
    'width_override',
    'height_override',
    'batch_size',
    'steps',
    'cfg',
    'seed'
]);
const DIMENSION_BINDING_FIELDS = new Set([
    'width',
    'height',
    'width_override',
    'height_override'
]);

function readDimensionFromForm(key: string): number | null {
    if (typeof document === 'undefined') return null;
    const el = document.querySelector(
        `[data-binding-key="${key}"] input[type="number"]`
    ) as HTMLInputElement | null;
    if (!el) return null;
    const n = Number(el.value);
    return Number.isNaN(n) ? null : Math.round(n);
}

function readLoraFromForm(key: string): string | null {
    if (typeof document === 'undefined') return null;
    const el = document.querySelector(`[data-binding-key="${key}"]`) as
        | HTMLInputElement
        | null;
    if (!el || typeof el.value !== 'string') return null;
    return el.value.trim() || null;
}

export function buildRunValues(
    base: Record<string, any>,
    workflowModel: WorkflowModel,
    bindings: WorkflowBinding[],
    defaultRuns = 1
): Record<string, any> {
    const out: Record<string, any> = {};
    const inputs = workflowModel.inputs ?? [];

    for (const input of inputs) {
        const isDimension =
            input.field && DIMENSION_BINDING_FIELDS.has(input.field);
        const isSeed = input.role === 'seed' || input.type === 'seed';
        let v: unknown = base[input.key];
        if (isDimension && typeof document !== 'undefined') {
            const fromDom = readDimensionFromForm(input.key);
            if (fromDom !== null) v = fromDom;
        }
        if (isSeed) {
            const fromBase = base[input.key];
            const numFromBase = fromBase != null ? Number(fromBase) : NaN;
            if (Number.isInteger(numFromBase) && numFromBase >= 0) {
                v = numFromBase;
            } else if (typeof document !== 'undefined') {
                const fromDom = readDimensionFromForm(input.key);
                if (fromDom !== null) v = fromDom;
            }
        }
        const isNumber =
            input.type === 'number' ||
            input.type === 'seed' ||
            (input.field && DIMENSION_FIELDS.has(input.field));
        const isMedia = input.type === 'image' || input.type === 'video' || input.type === 'audio';
        const isBoolean = input.type === 'boolean';
        const hasValue =
            v !== undefined &&
            v !== null &&
            (isMedia ? v !== '' : isNumber ? true : isBoolean ? v === true || v === false : v !== '');
        let val = hasValue
            ? v
            : (input.default ??
                  (input.type === 'number' || input.type === 'seed'
                      ? 0
                      : isMedia
                        ? ''
                        : isBoolean
                          ? false
                          : ''));
        if (isNumber && (typeof val === 'string' || typeof val === 'number'))
            val = Number(val);
        if (typeof val === 'number' && Number.isNaN(val))
            val = isMedia ? '' : 0;
        if (isBoolean && typeof val !== 'boolean')
            val = val === true || val === 'true' || val === 1;
        if (
            isMedia &&
            val != null &&
            typeof val === 'object' &&
            'filename' in val
        ) {
            const f = (val as { filename?: unknown }).filename;
            val = typeof f === 'string' ? f : '';
        }
        out[input.key] = val;
    }
    out.runs = Math.max(
        1,
        Math.min(200, Number(base.runs) || defaultRuns)
    );
    for (const b of bindings) {
        if (!(b.key in out) && b.key in base) out[b.key] = base[b.key];
    }
    for (const b of bindings) {
        if (!DIMENSION_BINDING_FIELDS.has(b.field)) continue;
        const fromDom = readDimensionFromForm(b.key);
        if (fromDom !== null && fromDom >= 0) out[b.key] = fromDom;
    }
    for (const b of bindings) {
        if (!b.field || !b.field.endsWith('.lora')) continue;
        const fromBase = base[b.key];
        const hasFromBase =
            typeof fromBase === 'string' && fromBase.trim() !== '';
        if (hasFromBase) {
            out[b.key] = fromBase;
        } else {
            const fromDom = readLoraFromForm(b.key);
            if (fromDom !== null) out[b.key] = fromDom;
        }
    }
    return out;
}

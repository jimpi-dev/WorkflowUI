import type { WorkflowModel, WorkflowInput, WorkflowOutput } from './types';
import { NODE_SPECS } from './nodes';

const WORKFLOW_UI_LINK_CLASS = 'WorkflowUILink';
const OUTPUT_TYPES = ['image', 'video', 'audio'] as const;
type OutputType = (typeof OUTPUT_TYPES)[number];

function isOutputType(t: string | undefined): t is OutputType {
    return t !== undefined && (OUTPUT_TYPES as readonly string[]).includes(t);
}

function parseWorkflowUILinkDefs(raw: unknown): Array<Record<string, unknown>> {
    if (Array.isArray(raw)) return raw;
    if (typeof raw === 'string' && raw.trim()) {
        try {
            const p = JSON.parse(raw);
            return Array.isArray(p) ? p : [];
        } catch {
            return [];
        }
    }
    return [];
}

function workflowUILinkField(slot: number, typ: string): string {
    if (typ === 'image') return `input_image_${slot}`;
    if (typ === 'video') return `input_video_${slot}`;
    if (typ === 'audio') return `input_audio_${slot}`;
    if (typ === 'boolean') return `input_boolean_${slot}`;
    if (typ === 'number' || typ === 'seed') return `input_number_${slot}`;
    return `input_text_${slot}`;
}

function inputDefsFromTypeWidgets(nodeInputs: Record<string, unknown>): Array<{ name: string; type: string }> {
    const result: Array<{ name: string; type: string }> = [];
    for (let i = 0; i < 8; i++) {
        const typ = (nodeInputs[`type_${i}`] ?? '').toString().trim().toLowerCase();
        if (!typ) continue;
        const name = (nodeInputs[`name_${i}`] ?? '').toString().trim();
        result.push({ name: name || `field_${i}`, type: typ });
    }
    return result;
}

function analyzeWorkflowUILinkNode(nodeId: string, node: Record<string, any>, workflow: Record<string, any>): WorkflowModel {
    const inputs: WorkflowInput[] = [];
    const bindings: { key: string; nodeId: string; field: string }[] = [];
    const nodeInputs = node.inputs ?? {};
    let inputDefs = inputDefsFromTypeWidgets(nodeInputs);
    if (inputDefs.length === 0) {
        inputDefs = parseWorkflowUILinkDefs(nodeInputs.input_definitions);
    }
    const nodeTitle = (node._meta?.title ?? 'WorkflowUILink').replaceAll('_', ' ');
    const metaTitle = node._meta?.title?.replaceAll('_', ' ') ?? undefined;

    for (let i = 0; i < inputDefs.length; i++) {
        const item = inputDefs[i];
        if (!item || typeof item !== 'object') continue;
        const name = item.name;
        if (!name || typeof name !== 'string') continue;
        const typ = String(item.type ?? 'text').toLowerCase();
        const field = workflowUILinkField(i, typ);
        const key = `${nodeId}.${field}`;
        const label = (item.label ?? name).replaceAll('_', ' ');
        const isSeed = typ === 'seed';
        inputs.push({
            key,
            label,
            role: isSeed ? 'seed' : 'parameter',
            parent: nodeTitle,
            type: ['text', 'number', 'seed', 'image', 'video', 'audio', 'select', 'boolean'].includes(typ)
                ? (typ as 'text' | 'number' | 'seed' | 'image' | 'video' | 'audio' | 'select' | 'boolean')
                : 'text',
            default: nodeInputs[field] ?? item.default,
            nodeId,
            field,
            classType: WORKFLOW_UI_LINK_CLASS,
            metaTitle,
            ...(name ? { name } : {}),
            ...(item.min != null && { min: Number(item.min) }),
            ...(item.max != null && { max: Number(item.max) }),
            ...(item.step != null && { step: Number(item.step) }),
            ...(item.slider != null && { slider: Boolean(item.slider) }),
            ...(Array.isArray(item.options) && { options: item.options as string[] }),
            ...(item.optionSource != null && { optionSource: String(item.optionSource) }),
        });
        bindings.push({ key, nodeId, field });
    }

    // Outputs from rest of graph (SaveImage etc.), not from WorkflowUILink
    const outputs: WorkflowOutput[] = [];
    for (const [nid, n] of Object.entries(workflow)) {
        if (nid === nodeId || !n || typeof n !== 'object') continue;
        const spec = NODE_SPECS[n.class_type];
        if (!spec?.outputs?.type) continue;
        const typ = spec.outputs.type as 'image' | 'video' | 'audio';
        const label = (n._meta?.title ?? n.class_type ?? nid).replaceAll('_', ' ');
        const outMetaTitle = n._meta?.title?.replaceAll('_', ' ') ?? undefined;
        outputs.push({ nodeId: nid, type: typ, label, metaTitle: outMetaTitle });
    }

    const formLabel = (nodeInputs.form_label ?? '').toString().trim() || undefined;
    return { inputs, outputs, bindings, ...(formLabel ? { form_label: formLabel } : {}) };
}

export function analyzeWorkflow(
    workflow: Record<string, any>,
    options?: { useWorkflowUILink?: boolean }
): WorkflowModel {
    const useWorkflowUILink = options?.useWorkflowUILink === true;

    if (useWorkflowUILink) {
        const entry = Object.entries(workflow).find(([, n]) => n && typeof n === 'object' && n.class_type === WORKFLOW_UI_LINK_CLASS);
        if (entry) {
            const [nodeId, node] = entry;
            return analyzeWorkflowUILinkNode(nodeId, node as Record<string, any>, workflow);
        }
    }

    const inputs: WorkflowInput[] = [];
    const bindings: { key: string; nodeId: string; field: string }[] = [];
    const outputs: WorkflowOutput[] = [];
    const internalNodesMap = new Map<string, string>();
    let imageInputIndex = 0;

    for (const [nodeId, node] of Object.entries(workflow)) {
        const spec = NODE_SPECS[node.class_type];

        if (node.class_type === 'CLIPTextEncode' && Array.isArray(node.inputs?.text)) {
            continue;
        }

        if (!spec) {
            const title = node._meta?.title;
            if (title === 'Prompt' && node.inputs && typeof node.inputs === 'object') {
                const textField = typeof node.inputs.value === 'string' ? 'value' : typeof node.inputs.text === 'string' ? 'text' : null;
                if (textField) {
                    const key = `${nodeId}.${textField}`;
                    const label = title.replaceAll('_', ' ') ?? 'Prompt';
                    const parent = node._meta?.title?.replaceAll('_', ' ') ?? node.class_type ?? nodeId;
                    const metaTitle = node._meta?.title?.replaceAll('_', ' ') ?? null;
                    inputs.push({
                        key,
                        label,
                        role: 'parameter',
                        parent,
                        type: 'text',
                        default: node.inputs[textField],
                        nodeId,
                        field: textField,
                        classType: node.class_type ?? 'Unknown',
                        metaTitle: metaTitle ?? undefined
                    });
                    bindings.push({ key, nodeId, field: textField });
                }
            }
            continue;
        }

        const nodeTitle =
            node._meta?.title?.replaceAll('_', ' ')
            ?? node.class_type;

        if (spec.fixedInputs) {

            const layoutRows = spec.layout?.rows ?? [];
            const layoutMap = buildLayoutMap(layoutRows);
            
            for (const [field, def] of Object.entries(spec.fixedInputs)) {
                if (!(field in node.inputs)) continue;

                const key = `${nodeId}.${field}`;
                const isSeed = def.type === 'seed';

                let label: string;
                if (field === 'text') {
                    label = nodeTitle;
                } else if (def.type === 'image') {
                    imageInputIndex += 1;
                    label = `${def.label ?? 'Image'} ${imageInputIndex}`;
                } else {
                    label = def.label
                        ? def.label
                        : `${nodeTitle} – ${field}`;
                }

                const layout = layoutMap[field];
                const metaTitle = node._meta?.title?.replaceAll('_', ' ') ?? null;
                inputs.push({
                    key,
                    label,
                    role: isSeed ? 'seed' : 'parameter',
                    parent: nodeTitle,
                    type: def.type,
                    hideLabel: def.hideLabel,
                    default: node.inputs[field],
                    nodeId,
                    field,
                    min: def.min,
                    max: def.max,
                    step: def.step,
                    slider: def.slider,
                    options: def.options,
                    optionSource: def.optionSource,
                    layoutRow: layout?.row,
                    layoutCol: layout?.col,
                    classType: node.class_type,
                    metaTitle: metaTitle ?? undefined
                });

                bindings.push({ key, nodeId, field });
            }
        }

        if (spec.repeatGroups) {
            for (const group of spec.repeatGroups) {

                const layoutRows = group.layout?.rows ?? [];
                const layoutMap = buildLayoutMap(layoutRows);
                
                for (const [inputKey, inputValue] of Object.entries(node.inputs)) {
                    if (!group.match.test(inputKey)) continue;

                    if (typeof inputValue !== 'object') continue;

                    for (const [fieldKey, fieldSpec] of Object.entries(group.fields)) {
                        if (!(fieldKey in inputValue)) continue;

                        const key = `${nodeId}.${inputKey}.${fieldKey}`;

                        const layout = layoutMap[fieldKey];
                        
                        const raw = inputValue[fieldKey];
                        const defaultVal =
                            fieldKey === 'lora' && typeof raw === 'string'
                                ? raw.split('/').pop()?.replace('.safetensors', '') ?? raw
                                : raw;
                        const metaTitle = node._meta?.title?.replaceAll('_', ' ') ?? null;
                        inputs.push({
                            key,
                            label: fieldSpec.label,
                            role: 'parameter',
                            parent: nodeTitle,
                            type: fieldSpec.type,
                            hideLabel: fieldSpec.hideLabel,
                            default: defaultVal,
                            nodeId,
                            field: `${inputKey}.${fieldKey}`,
                            min: fieldSpec.min,
                            max: fieldSpec.max,
                            step: fieldSpec.step,
                            slider: fieldSpec.slider,
                            options: fieldSpec.options,
                            optionSource: fieldSpec.optionSource,
                            layoutRow: layout?.row,
                            layoutCol: layout?.col,
                            classType: node.class_type,
                            groupKey: inputKey,
                            metaTitle: metaTitle ?? undefined
                        });

                        bindings.push({
                            key,
                            nodeId,
                            field: `${inputKey}.${fieldKey}`
                        });
                    }
                }
            }
        }

        if (isOutputType(spec.outputs?.type)) {
            const label = node._meta?.title?.replaceAll('_', ' ') ?? node.class_type?.replace(/([A-Z])/g, ' $1').trim() ?? nodeId;
            const metaTitle = node._meta?.title?.replaceAll('_', ' ') ?? null;
            outputs.push({ nodeId, type: spec.outputs.type, label, metaTitle: metaTitle ?? undefined });
        }

        const hasNoFixedInputs = !spec.fixedInputs || Object.keys(spec.fixedInputs).length === 0;
        const hasNoRepeatGroups = !spec.repeatGroups || spec.repeatGroups.length === 0;
        const hasNoOutputs = !spec.outputs?.type;
        if (hasNoFixedInputs && hasNoRepeatGroups && hasNoOutputs) {
            const label = node._meta?.title?.replaceAll('_', ' ') ?? node.class_type?.replace(/([A-Z])/g, ' $1').trim() ?? nodeId;
            internalNodesMap.set(node.class_type, label);
        }
    }

    return { 
        inputs, 
        outputs, 
        bindings,
        internalNodes: internalNodesMap.size > 0
            ? Array.from(internalNodesMap.entries()).map(([classType, label]) => ({ classType, label }))
            : undefined
    };
}

function buildLayoutMap(rows: string[][]) {

    const map: Record<string, { row: number; col: number }> = {};

    rows.forEach((row, rowIndex) => {
        row.forEach((fieldName, colIndex) => {
            map[fieldName] = {
                row: rowIndex,
                col: colIndex
            };
        });
    });

    return map;
}

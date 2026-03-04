export type InputOverride = {
	label?: string;
	description?: string;
	min?: number;
	max?: number;
	step?: number;
};

export type AppDraft = {
	visibleInputs: Set<string>;
	defaultOverrides: Map<string, unknown>;
	inputOverrides: Map<string, InputOverride>;
	visibleOutputs: Set<string>;
	primaryOutput: string | null;
	outputLabels: Map<string, string>;
	inputNodeOrder: string[];
	outputNodeOrder: string[];
	masterSeedInputKey: string | null;
	ignoreLoadImageDefault: boolean;
};

export type UIConfig = {
	visibleInputs: string[];
	inputOverrides: Record<string, InputOverride>;
	visibleOutputs: string[];
	primaryOutput: string | null;
	outputLabels?: Record<string, string>;
	inputNodeOrder?: string[];
	outputNodeOrder?: string[];
	masterSeedInputKey?: string | null;
	ignoreLoadImageDefault?: boolean;
};

export function nodeIdFromInputKey(key: string): string {
	return key.split('.')[0] ?? key;
}

function defaultInputNodeOrder(inputKeys: string[]): string[] {
	const seen = new Set<string>();
	const order: string[] = [];
	for (const k of inputKeys) {
		const nid = nodeIdFromInputKey(k);
		if (!seen.has(nid)) {
			seen.add(nid);
			order.push(nid);
		}
	}
	return order;
}

export function createEmptyDraft(
	inputKeys: string[],
	outputKeys: string[]
): AppDraft {
	const visibleInputs = new Set(inputKeys);
	const visibleOutputs = new Set(outputKeys);
	const primaryOutput = outputKeys.length > 0 ? outputKeys[0] : null;
	return {
		visibleInputs,
		defaultOverrides: new Map(),
		inputOverrides: new Map(),
		visibleOutputs,
		primaryOutput,
		outputLabels: new Map(),
		inputNodeOrder: defaultInputNodeOrder(inputKeys),
		outputNodeOrder: [...outputKeys],
		masterSeedInputKey: null,
		ignoreLoadImageDefault: false
	};
}

export function draftFromExistingApp(
	inputKeys: string[],
	outputKeys: string[],
	uiConfig: UIConfig | null,
	defaultInputs: Record<string, unknown> | null
): AppDraft {
	const visibleInputs = new Set(uiConfig?.visibleInputs ?? inputKeys);
	const visibleOutputs = new Set(uiConfig?.visibleOutputs ?? outputKeys);
	const primaryOutput = uiConfig?.primaryOutput ?? outputKeys[0] ?? null;
	const defaultOverrides = new Map<string, unknown>();
	if (defaultInputs && typeof defaultInputs === 'object') {
		for (const [k, v] of Object.entries(defaultInputs)) {
			defaultOverrides.set(k, v);
		}
	}
	const inputOverrides = new Map<string, InputOverride>();
	if (uiConfig?.inputOverrides && typeof uiConfig.inputOverrides === 'object') {
		for (const [k, v] of Object.entries(uiConfig.inputOverrides)) {
			if (v && typeof v === 'object') inputOverrides.set(k, v);
		}
	}
	const outputLabels = new Map<string, string>();
	if (uiConfig?.outputLabels && typeof uiConfig.outputLabels === 'object') {
		for (const [k, v] of Object.entries(uiConfig.outputLabels)) {
			if (typeof v === 'string' && v.trim()) outputLabels.set(k, v.trim());
		}
	}
	const inputNodeOrder =
		Array.isArray(uiConfig?.inputNodeOrder) && uiConfig.inputNodeOrder.length > 0
			? uiConfig.inputNodeOrder
			: defaultInputNodeOrder(inputKeys);
	const outputNodeOrder =
		Array.isArray(uiConfig?.outputNodeOrder) && uiConfig.outputNodeOrder.length > 0
			? uiConfig.outputNodeOrder
			: [...outputKeys];
	const masterSeedInputKey =
		typeof uiConfig?.masterSeedInputKey === 'string' && uiConfig.masterSeedInputKey.trim()
			? uiConfig.masterSeedInputKey.trim()
			: null;
	const ignoreLoadImageDefault = uiConfig?.ignoreLoadImageDefault === true;
	return {
		visibleInputs,
		defaultOverrides,
		inputOverrides,
		visibleOutputs,
		primaryOutput,
		outputLabels,
		inputNodeOrder,
		outputNodeOrder,
		masterSeedInputKey,
		ignoreLoadImageDefault
	};
}

export function draftToUIConfig(draft: AppDraft): UIConfig {
	const visibleOutputsList = Array.from(draft.visibleOutputs);
	let primary = draft.primaryOutput;
	if (primary && !draft.visibleOutputs.has(primary)) primary = null;
	if (!primary && visibleOutputsList.length > 0) primary = visibleOutputsList[0];
	const outputLabelsObj: Record<string, string> = {};
	for (const [k, v] of draft.outputLabels) {
		if (v.trim()) outputLabelsObj[k] = v;
	}
	return {
		visibleInputs: Array.from(draft.visibleInputs),
		inputOverrides: Object.fromEntries(draft.inputOverrides),
		visibleOutputs: visibleOutputsList,
		primaryOutput: primary,
		...(Object.keys(outputLabelsObj).length > 0 ? { outputLabels: outputLabelsObj } : {}),
		inputNodeOrder: draft.inputNodeOrder,
		outputNodeOrder: draft.outputNodeOrder,
		...(draft.masterSeedInputKey != null && draft.masterSeedInputKey !== '' ? { masterSeedInputKey: draft.masterSeedInputKey } : {}),
		...(draft.ignoreLoadImageDefault ? { ignoreLoadImageDefault: true } : {})
	};
}

export function draftToDefaultInputs(draft: AppDraft): Record<string, unknown> {
	return Object.fromEntries(draft.defaultOverrides);
}

export function setInputVisible(draft: AppDraft, key: string, visible: boolean): void {
	if (visible) draft.visibleInputs.add(key);
	else draft.visibleInputs.delete(key);
}

export function setDefaultOverride(draft: AppDraft, key: string, value: unknown): void {
	if (value === undefined || value === '') draft.defaultOverrides.delete(key);
	else draft.defaultOverrides.set(key, value);
}

export function setInputOverride(draft: AppDraft, key: string, override: InputOverride | null): void {
	if (!override || Object.keys(override).length === 0) draft.inputOverrides.delete(key);
	else draft.inputOverrides.set(key, override);
}

export function setOutputVisible(draft: AppDraft, outputId: string, visible: boolean): void {
	if (visible) {
		draft.visibleOutputs.add(outputId);
		if (!draft.primaryOutput && draft.visibleOutputs.size === 1) draft.primaryOutput = outputId;
	} else {
		draft.visibleOutputs.delete(outputId);
		if (draft.primaryOutput === outputId) {
			const rest = Array.from(draft.visibleOutputs).filter((id) => id !== outputId);
			draft.primaryOutput = rest[0] ?? null;
		}
	}
}

export function setPrimaryOutput(draft: AppDraft, outputId: string): void {
	if (draft.visibleOutputs.has(outputId)) draft.primaryOutput = outputId;
}

export function setOutputLabel(draft: AppDraft, outputId: string, label: string): void {
	const trimmed = label.trim();
	if (trimmed) draft.outputLabels.set(outputId, trimmed);
	else draft.outputLabels.delete(outputId);
}

export function moveInputNodeOrder(draft: AppDraft, nodeId: string, direction: 'up' | 'down'): void {
	const order = draft.inputNodeOrder;
	const i = order.indexOf(nodeId);
	if (i < 0) return;
	if (direction === 'up' && i > 0) {
		[order[i - 1], order[i]] = [order[i], order[i - 1]];
	} else if (direction === 'down' && i < order.length - 1) {
		[order[i], order[i + 1]] = [order[i + 1], order[i]];
	}
}

export function moveOutputNodeOrder(draft: AppDraft, nodeId: string, direction: 'up' | 'down'): void {
	const order = draft.outputNodeOrder;
	const i = order.indexOf(nodeId);
	if (i < 0) return;
	if (direction === 'up' && i > 0) {
		[order[i - 1], order[i]] = [order[i], order[i - 1]];
	} else if (direction === 'down' && i < order.length - 1) {
		[order[i], order[i + 1]] = [order[i + 1], order[i]];
	}
}

export function setMasterSeedInputKey(draft: AppDraft, key: string | null): void {
	draft.masterSeedInputKey = key && key.trim() ? key.trim() : null;
}

/** Prefer input with name "seed" (case-insensitive) for master seed; else first seed input. */
export function getDefaultMasterSeedInputKey(
	inputs: { key?: string; type?: string; name?: string }[]
): string | null {
	const seedInputs = inputs.filter(
		(i) => (i.type === 'seed' || (i as { role?: string }).role === 'seed') && i.key?.trim()
	);
	if (seedInputs.length === 0) return null;
	const namedSeed = seedInputs.find(
		(i) => (i.name ?? '').toLowerCase().trim() === 'seed'
	);
	return (namedSeed?.key ?? seedInputs[0]?.key)?.trim() ?? null;
}

export function setIgnoreLoadImageDefault(draft: AppDraft, value: boolean): void {
	draft.ignoreLoadImageDefault = value;
}

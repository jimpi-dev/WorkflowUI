import { analyzeWorkflow } from '$lib/workflow';
import { appConfig, getApiBase } from '$lib/config';

export const ssr = appConfig.ssr;

function bindingsFromInputs(
	inputs: { key?: string; nodeId?: string; field?: string }[]
): { key: string; nodeId: string; field: string }[] {
	return inputs
		.filter((i) => i && i.key != null && i.nodeId != null && i.field != null)
		.map((i) => ({ key: i.key!, nodeId: i.nodeId!, field: i.field! }));
}

function filenameFromRunOutput(ent: unknown): string | undefined {
	if (ent && typeof ent === 'object' && 'filename' in ent) {
		const f = (ent as { filename?: unknown }).filename;
		return typeof f === 'string' ? f : undefined;
	}
	return undefined;
}

export const load = async ({ params, fetch, url }) => {
	try {
		const apiBase = getApiBase() || '';
		let sendFromRun: string | null = null;
		let sendFromOutput: string | null = null;
		try {
			sendFromRun = url.searchParams.get('send_from_run');
			sendFromOutput = url.searchParams.get('send_from_output');
		} catch {
		}
		const [appRes, cfgRes] = await Promise.all([
			fetch(`${apiBase}/app/${params.id}`),
			fetch(`${apiBase}/config`)
		]);
		let comfyuiDeleteSupported = false;
		let embedWorkflowuiMetadataOnDownload = false;
		let embedWorkflowuiMetadataOnSave = false;
		if (cfgRes.ok) {
			try {
				const cfg = await cfgRes.json();
				comfyuiDeleteSupported = cfg.comfyuiDeleteSupported === true;
				embedWorkflowuiMetadataOnDownload = cfg.embedWorkflowuiMetadataOnDownload === true;
				embedWorkflowuiMetadataOnSave = cfg.embedWorkflowuiMetadataOnSave === true;
			} catch {
			}
		}
		
		if (appRes.status === 404) {
			return { appRemoved: true, workflowId: params.id, comfyuiDeleteSupported, sendFromPreload: null };
		}
		if (appRes.ok) {
			const appData = await appRes.json();
			const wv = appData.workflow_version ?? {};
			const app = appData.app ?? {};
		
			if (typeof app.embedWorkflowuiMetadataOnDownload === 'boolean') {
				embedWorkflowuiMetadataOnDownload = app.embedWorkflowuiMetadataOnDownload;
			}
			if (typeof app.embedWorkflowuiMetadataOnSave === 'boolean') {
				embedWorkflowuiMetadataOnSave = app.embedWorkflowuiMetadataOnSave;
			}
			const uiConfig = app.ui_config as { visibleInputs?: string[]; inputOverrides?: Record<string, { label?: string; description?: string; min?: number; max?: number; step?: number }>; visibleOutputs?: string[]; primaryOutput?: string | null; outputLabels?: Record<string, string>; inputNodeOrder?: string[]; outputNodeOrder?: string[]; masterSeedInputKey?: string | null } | undefined;
			let detectedInputs = Array.isArray(wv.detected_inputs) ? [...wv.detected_inputs] : [];
			let detectedOutputs = Array.isArray(wv.detected_outputs) ? [...wv.detected_outputs] : [];
			if (uiConfig?.inputNodeOrder && Array.isArray(uiConfig.inputNodeOrder) && uiConfig.inputNodeOrder.length > 0) {
				const order = uiConfig.inputNodeOrder;
				const byNode = new Map<string, (typeof detectedInputs)[number][]>();
				for (const i of detectedInputs) {
					const nid = (i as { nodeId?: string }).nodeId ?? (i.key ? String(i.key).split('.')[0] : '');
					if (!byNode.has(nid)) byNode.set(nid, []);
					byNode.get(nid)!.push(i);
				}
				const sorted: typeof detectedInputs = [];
				for (const nid of order) {
					const list = byNode.get(nid);
					if (list) sorted.push(...list);
				}
				for (const [nid, list] of byNode) {
					if (!order.includes(nid)) sorted.push(...list);
				}
				detectedInputs = sorted;
			}
			// Apply input visibility (from app builder)
			if (uiConfig?.visibleInputs && Array.isArray(uiConfig.visibleInputs) && uiConfig.visibleInputs.length > 0) {
				const visibleSet = new Set(uiConfig.visibleInputs);
				detectedInputs = detectedInputs.filter((i: { key?: string }) => i.key && visibleSet.has(i.key));
			}
			
			if (uiConfig?.inputOverrides && typeof uiConfig.inputOverrides === 'object') {
				for (const input of detectedInputs) {
					const o = uiConfig.inputOverrides[(input as { key: string }).key];
					if (o && typeof o === 'object') {
						if (o.label != null) (input as Record<string, unknown>).label = o.label;
						if (o.description != null) (input as Record<string, unknown>).description = o.description;
						if (o.min != null) (input as Record<string, unknown>).min = o.min;
						if (o.max != null) (input as Record<string, unknown>).max = o.max;
						if (o.step != null) (input as Record<string, unknown>).step = o.step;
					}
				}
			}
			const defaultInputs = app.default_inputs && typeof app.default_inputs === 'object' ? app.default_inputs as Record<string, unknown> : {};
			
			for (const input of detectedInputs) {
				if (input.key && input.key in defaultInputs) {
					(input as Record<string, unknown>).default = defaultInputs[input.key];
				}
			}
			
			if ((uiConfig as { ignoreLoadImageDefault?: boolean })?.ignoreLoadImageDefault) {
				for (const input of detectedInputs) {
					if ((input as { type?: string }).type === 'image') {
						(input as Record<string, unknown>).default = '';
					}
				}
			}
			
			if (uiConfig?.visibleOutputs && Array.isArray(uiConfig.visibleOutputs) && uiConfig.visibleOutputs.length > 0) {
				const visibleSet = new Set(uiConfig.visibleOutputs);
				detectedOutputs = detectedOutputs.filter((o: { nodeId?: string }) => o.nodeId && visibleSet.has(o.nodeId));
			
				if (uiConfig?.outputNodeOrder && Array.isArray(uiConfig.outputNodeOrder) && uiConfig.outputNodeOrder.length > 0) {
					const order = uiConfig.outputNodeOrder;
					const byId = new Map(detectedOutputs.map((o: { nodeId: string }) => [o.nodeId, o]));
					const sorted: typeof detectedOutputs = [];
					for (const nid of order) {
						const o = byId.get(nid);
						if (o) sorted.push(o);
					}
					for (const o of detectedOutputs) {
						if (o.nodeId && !order.includes(o.nodeId)) sorted.push(o);
					}
					detectedOutputs = sorted;
				}
				const primary = uiConfig.primaryOutput;
				if (primary && visibleSet.has(primary)) {
					const primaryOut = detectedOutputs.find((o: { nodeId: string }) => o.nodeId === primary);
					const rest = detectedOutputs.filter((o: { nodeId: string }) => o.nodeId !== primary);
					if (primaryOut) detectedOutputs = [primaryOut, ...rest];
				}
			}
			
			if (uiConfig?.outputLabels && typeof uiConfig.outputLabels === 'object') {
				for (const output of detectedOutputs) {
					const id = (output as { nodeId?: string }).nodeId;
					if (id && id in uiConfig.outputLabels) {
						(output as Record<string, unknown>).label = uiConfig.outputLabels[id];
					}
				}
			}
			const bindings = bindingsFromInputs(detectedInputs);
			// Master seed: pass through from ui_config so runner uses it; AutoForm resolves by key (falls back to first seed if not found).
			const rawMasterSeed =
				(uiConfig as Record<string, unknown>)?.masterSeedInputKey ??
				(uiConfig as Record<string, unknown>)?.master_seed_input_key;
			const masterSeedInputKey =
				typeof rawMasterSeed === 'string' && rawMasterSeed.trim()
					? rawMasterSeed.trim()
					: undefined;
			const workflowModel = {
				inputs: detectedInputs,
				outputs: detectedOutputs,
				bindings,
				...(masterSeedInputKey ? { masterSeedInputKey } : {})
			};
			const [listRes, objectInfoRes, lorasRes, lycorisTypesRes, checkpointsRes, devicesRes, rifeModelsRes, unetGgufModelsRes, stableCascadeModelsRes] = await Promise.all([
				fetch(`${apiBase}/workflows`),
				fetch(`${apiBase}/object_info`).catch(() => null),
				fetch(`${apiBase}/loras`).catch(() => null),
				fetch(`${apiBase}/lycoris_types`).catch(() => null),
				fetch(`${apiBase}/checkpoints`).catch(() => null),
				fetch(`${apiBase}/devices`).catch(() => null),
				fetch(`${apiBase}/rife_models`).catch(() => null),
				fetch(`${apiBase}/unet_gguf_models`).catch(() => null),
				fetch(`${apiBase}/stable_cascade_models`).catch(() => null)
			]);
			const objectInfo = objectInfoRes?.ok ? await objectInfoRes.json() : { samplers: [], schedulers: [] };
			const { samplers = [], schedulers = [] } = objectInfo;
			const loras = lorasRes?.ok ? (await lorasRes.json())?.loras ?? [] : [];
			const lycorisTypes = lycorisTypesRes?.ok ? (await lycorisTypesRes.json())?.lycoris_types ?? [] : [];
			const checkpoints = checkpointsRes?.ok ? (await checkpointsRes.json())?.checkpoints ?? [] : [];
			const devices = devicesRes?.ok ? (await devicesRes.json())?.devices ?? [] : [];
			const rifeModels = rifeModelsRes?.ok ? (await rifeModelsRes.json())?.rife_models ?? [] : [];
			const unetGgufModels = unetGgufModelsRes?.ok ? (await unetGgufModelsRes.json())?.unet_gguf_models ?? [] : [];
			const stableCascadeModels = stableCascadeModelsRes?.ok ? (await stableCascadeModelsRes.json()) ?? {} : {};
			const stableCascadeStageB = Array.isArray(stableCascadeModels.stage_b) ? stableCascadeModels.stage_b : [];
			const stableCascadeStageC = Array.isArray(stableCascadeModels.stage_c) ? stableCascadeModels.stage_c : [];
			for (const input of workflowModel.inputs) {
				if (input.optionSource === 'samplers' && samplers.length) input.options = samplers;
				if (input.optionSource === 'schedulers' && schedulers.length) input.options = schedulers;
				if (input.optionSource === 'loras' && Array.isArray(loras) && loras.length) input.options = loras;
				if (input.optionSource === 'lycoris_types' && Array.isArray(lycorisTypes) && lycorisTypes.length) input.options = lycorisTypes;
				if (input.optionSource === 'checkpoints' && Array.isArray(checkpoints) && checkpoints.length) input.options = checkpoints;
				if (input.optionSource === 'devices' && Array.isArray(devices) && devices.length) input.options = devices;
				if (input.optionSource === 'rife_models' && Array.isArray(rifeModels) && rifeModels.length) input.options = rifeModels;
				if (input.optionSource === 'unet_gguf_models' && Array.isArray(unetGgufModels) && unetGgufModels.length) input.options = unetGgufModels;
				if (input.optionSource === 'stable_cascade_stage_b' && stableCascadeStageB.length) input.options = stableCascadeStageB;
				if (input.optionSource === 'stable_cascade_stage_c' && stableCascadeStageC.length) input.options = stableCascadeStageC;
			}
			const workflows = listRes.ok ? await listRes.json() : [];
			const workflowLoraPaths = extractLoraPathsFromDetectedInputs(detectedInputs);
			
			let sendFromPreload: { runId: string; outputIndex: number; inputKey: string; filename: string; subfolder: string; type: string } | null = null;
			if (sendFromRun && sendFromOutput != null && apiBase) {
				const outputIndex = parseInt(sendFromOutput, 10);
				const firstImageInput = detectedInputs.find((i: { type?: string }) => (i as { type?: string }).type === 'image') as { key: string } | undefined;
				if (!Number.isNaN(outputIndex) && outputIndex >= 0 && firstImageInput?.key) {
					try {
						const runRes = await fetch(`${apiBase}/runs/${sendFromRun}`);
						if (runRes.ok) {
							const run = await runRes.json();
							const list = run?.media ?? run?.images;
							const arr = Array.isArray(list) ? list : [];
							if (outputIndex < arr.length) {
								const ent = arr[outputIndex];
								const filename = filenameFromRunOutput(ent);
								if (filename) {
									const subfolder = ent && typeof ent === 'object' && 'subfolder' in ent ? String((ent as { subfolder?: unknown }).subfolder ?? '') : '';
									const type = ent && typeof ent === 'object' && ('type' in ent || 'kind' in ent)
										? String((ent as { type?: string; kind?: string }).type ?? (ent as { kind?: string }).kind ?? 'image')
										: 'image';
									sendFromPreload = { runId: sendFromRun, outputIndex, inputKey: firstImageInput.key, filename, subfolder, type };
								}
							}
						}
					} catch {
						// ignore
					}
				}
			}
			return {
				workflowJson: null,
				workflowModel,
				workflowLoraPaths,
				workflowId: app.slug ?? params.id,
				workflows,
				appId: app.id ?? null,
				appConfig: app,
				isAppBySlug: true,
				comfyuiDeleteSupported,
				embedWorkflowuiMetadataOnDownload,
				embedWorkflowuiMetadataOnSave,
				sendFromPreload
			};
		}
		
		const [wfRes, listRes, objectInfoRes, lorasRes, lycorisTypesRes, checkpointsRes, devicesRes, rifeModelsRes, unetGgufModelsRes, stableCascadeModelsRes] = await Promise.all([
			fetch(`${apiBase}/workflow/${params.id}`),
			fetch(`${apiBase}/workflows`),
			fetch(`${apiBase}/object_info`).catch(() => null),
			fetch(`${apiBase}/loras`).catch(() => null),
			fetch(`${apiBase}/lycoris_types`).catch(() => null),
			fetch(`${apiBase}/checkpoints`).catch(() => null),
			fetch(`${apiBase}/devices`).catch(() => null),
			fetch(`${apiBase}/rife_models`).catch(() => null),
			fetch(`${apiBase}/unet_gguf_models`).catch(() => null),
			fetch(`${apiBase}/stable_cascade_models`).catch(() => null)
		]);

		if (!wfRes.ok) {
			const body = await wfRes.json().catch(() => ({}));
			const msg = (body as { detail?: string }).detail ?? `Workflow failed to load: ${wfRes.status}`;
			throw new Error(msg);
		}
		const workflowJson = await wfRes.json();
		if (!workflowJson || typeof workflowJson !== 'object') {
			throw new Error('Invalid workflow response');
		}
		const workflowModel = analyzeWorkflow(workflowJson);

		const workflowLoraPaths = extractLoraPathsFromWorkflow(workflowJson as Record<string, unknown>);

		const objectInfo = objectInfoRes?.ok ? await objectInfoRes.json() : { samplers: [], schedulers: [] };
		const { samplers = [], schedulers = [] } = objectInfo;
		const loras = lorasRes?.ok ? (await lorasRes.json())?.loras ?? [] : [];
		const lycorisTypes = lycorisTypesRes?.ok ? (await lycorisTypesRes.json())?.lycoris_types ?? [] : [];
		const checkpoints = checkpointsRes?.ok ? (await checkpointsRes.json())?.checkpoints ?? [] : [];
		const devices = devicesRes?.ok ? (await devicesRes.json())?.devices ?? [] : [];
		const rifeModels = rifeModelsRes?.ok ? (await rifeModelsRes.json())?.rife_models ?? [] : [];
		const unetGgufModels = unetGgufModelsRes?.ok ? (await unetGgufModelsRes.json())?.unet_gguf_models ?? [] : [];
		const stableCascadeModels = stableCascadeModelsRes?.ok ? (await stableCascadeModelsRes.json()) ?? {} : {};
		const stableCascadeStageB = Array.isArray(stableCascadeModels.stage_b) ? stableCascadeModels.stage_b : [];
		const stableCascadeStageC = Array.isArray(stableCascadeModels.stage_c) ? stableCascadeModels.stage_c : [];

		for (const input of workflowModel.inputs) {
			if (input.optionSource === 'samplers' && samplers.length) {
				input.options = samplers;
			}
			if (input.optionSource === 'schedulers' && schedulers.length) {
				input.options = schedulers;
			}
			if (input.optionSource === 'loras' && Array.isArray(loras) && loras.length) {
				input.options = loras;
			}
			if (input.optionSource === 'lycoris_types' && Array.isArray(lycorisTypes) && lycorisTypes.length) {
				input.options = lycorisTypes;
			}
			if (input.optionSource === 'checkpoints' && Array.isArray(checkpoints) && checkpoints.length) {
				input.options = checkpoints;
			}
			if (input.optionSource === 'devices' && Array.isArray(devices) && devices.length) {
				input.options = devices;
			}
			if (input.optionSource === 'rife_models' && Array.isArray(rifeModels) && rifeModels.length) {
				input.options = rifeModels;
			}
			if (input.optionSource === 'unet_gguf_models' && Array.isArray(unetGgufModels) && unetGgufModels.length) {
				input.options = unetGgufModels;
			}
			if (input.optionSource === 'stable_cascade_stage_b' && stableCascadeStageB.length) {
				input.options = stableCascadeStageB;
			}
			if (input.optionSource === 'stable_cascade_stage_c' && stableCascadeStageC.length) {
				input.options = stableCascadeStageC;
			}
		}

		const workflows = listRes.ok ? await listRes.json() : [];

		return {
			workflowJson,
			workflowModel,
			workflowLoraPaths,
			workflowId: params.id,
			workflows,
			appId: null,
			appConfig: null,
			isAppBySlug: false,
			comfyuiDeleteSupported,
			embedWorkflowuiMetadataOnDownload,
			embedWorkflowuiMetadataOnSave,
			sendFromPreload: null
		};
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err);
		throw new Error(`Page load failed: ${message}`);
	}
};

function extractLoraPathsFromWorkflow(workflow: Record<string, unknown>): string[] {
	const paths = new Set<string>();
	for (const node of Object.values(workflow)) {
		if (!node || typeof node !== 'object' || !('inputs' in node)) continue;
		const inputs = (node as { inputs: Record<string, unknown> }).inputs;
		if (!inputs || typeof inputs !== 'object') continue;
		const loraName = inputs.lora_name;
		if (typeof loraName === 'string' && loraName.trim()) paths.add(loraName.trim());
		for (const key of Object.keys(inputs)) {
			if (!/^lora_\d+$/.test(key)) continue;
			const slot = inputs[key];
			if (slot && typeof slot === 'object' && 'lora' in slot) {
				const lora = (slot as { lora: unknown }).lora;
				if (typeof lora === 'string' && lora.trim()) paths.add(lora.trim());
			}
		}
	}
	return Array.from(paths).sort();
}

function extractLoraPathsFromDetectedInputs(inputs: { key?: string; default?: unknown }[]): string[] {
	const paths = new Set<string>();
	for (const input of inputs) {
		const v = input.default;
		if (typeof v === 'string' && v.trim() && (v.endsWith('.safetensors') || v.includes('/')))
			paths.add(v.trim());
	}
	return Array.from(paths).sort();
}

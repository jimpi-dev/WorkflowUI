import { describe, it, expect } from 'vitest';
import { analyzeWorkflow } from './analyze';

describe('analyzeWorkflow', () => {
	it('detects inputs and outputs from a minimal workflow', () => {
		const workflow = {
			'7': {
				class_type: 'CLIPTextEncode',
				inputs: { text: 'hello' },
				_meta: { title: 'CLIP Text Encode (Prompt)' }
			},
			'9': {
				class_type: 'KSampler',
				inputs: { seed: 12345, steps: 20, cfg: 7.5, sampler_name: 'euler' }
			},
			'10': {
				class_type: 'SaveImage',
				inputs: {}
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.inputs).toBeDefined();
		expect(result.inputs.length).toBeGreaterThan(0);
		expect(result.outputs).toBeDefined();
		expect(result.outputs.length).toBe(1);
		expect(result.outputs[0]).toEqual({ nodeId: '10', type: 'image', label: 'Save Image' });
		expect(result.bindings.length).toBe(result.inputs.length);
	});

	it('includes CLIPTextEncode text input with correct key and label', () => {
		const workflow = {
			'7': {
				class_type: 'CLIPTextEncode',
				inputs: { text: 'a prompt' },
				_meta: { title: 'CLIP Text Encode (Prompt)' }
			}
		};

		const result = analyzeWorkflow(workflow);

		const textInput = result.inputs.find((i) => i.field === 'text' && i.classType === 'CLIPTextEncode');
		expect(textInput).toBeDefined();
		expect(textInput?.key).toBe('7.text');
		expect(textInput?.label).toBe('CLIP Text Encode (Prompt)');
		expect(textInput?.type).toBe('text');
		expect(textInput?.default).toBe('a prompt');
	});

	it('includes KSampler seed and number inputs', () => {
		const workflow = {
			'9': {
				class_type: 'KSampler',
				inputs: { seed: 42, steps: 25, cfg: 8, sampler_name: 'euler' }
			}
		};

		const result = analyzeWorkflow(workflow);

		const seedInput = result.inputs.find((i) => i.field === 'seed');
		expect(seedInput).toBeDefined();
		expect(seedInput?.type).toBe('seed');
		expect(seedInput?.role).toBe('seed');
		expect(seedInput?.default).toBe(42);

		const stepsInput = result.inputs.find((i) => i.field === 'steps');
		expect(stepsInput).toBeDefined();
		expect(stepsInput?.type).toBe('number');
		expect(stepsInput?.default).toBe(25);
	});

	it('skips CLIPTextEncode when text is a node reference (passthrough)', () => {
		const workflow = {
			'7': {
				class_type: 'CLIPTextEncode',
				inputs: { text: ['58', 0] }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.inputs.filter((i) => i.nodeId === '7')).toHaveLength(0);
	});

	it('detects VHS_VideoCombine as video output', () => {
		const workflow = {
			'129': {
				class_type: 'VHS_VideoCombine',
				inputs: {},
				_meta: { title: 'Save Video - Base' }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.outputs).toHaveLength(1);
		expect(result.outputs[0]).toEqual({
			nodeId: '129',
			type: 'video',
			label: 'Save Video - Base',
			metaTitle: 'Save Video - Base'
		});
	});

	it('returns empty inputs and outputs for empty workflow', () => {
		const result = analyzeWorkflow({});

		expect(result.inputs).toEqual([]);
		expect(result.outputs).toEqual([]);
		expect(result.bindings).toEqual([]);
		expect(result.internalNodes).toBeUndefined();
	});

	it('includes EmptyLatentImage width/height inputs and bindings so dimensions are honored', () => {
		const workflow = {
			'5': {
				class_type: 'EmptyLatentImage',
				inputs: { width: 512, height: 512, batch_size: 1 }
			}
		};

		const result = analyzeWorkflow(workflow);

		const widthInput = result.inputs.find((i) => i.key === '5.width');
		const heightInput = result.inputs.find((i) => i.key === '5.height');
		expect(widthInput).toBeDefined();
		expect(heightInput).toBeDefined();
		expect(widthInput?.type).toBe('number');
		expect(heightInput?.type).toBe('number');

		const widthBinding = result.bindings.find((b) => b.key === '5.width');
		const heightBinding = result.bindings.find((b) => b.key === '5.height');
		expect(widthBinding).toBeDefined();
		expect(heightBinding).toBeDefined();
		expect(widthBinding?.nodeId).toBe('5');
		expect(widthBinding?.field).toBe('width');
		expect(heightBinding?.nodeId).toBe('5');
		expect(heightBinding?.field).toBe('height');
	});

	it('uses Prompt fallback for unknown node with _meta.title "Prompt" and text/value input', () => {
		const workflow = {
			'99': {
				class_type: 'CustomPromptNode',
				inputs: { value: 'custom prompt text' },
				_meta: { title: 'Prompt' }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.inputs).toHaveLength(1);
		expect(result.inputs[0]).toMatchObject({
			key: '99.value',
			label: 'Prompt',
			type: 'text',
			role: 'parameter',
			nodeId: '99',
			field: 'value',
			classType: 'CustomPromptNode',
			default: 'custom prompt text'
		});
		expect(result.bindings).toHaveLength(1);
		expect(result.bindings[0]).toEqual({ key: '99.value', nodeId: '99', field: 'value' });
	});

	it('uses Prompt fallback when prompt node uses "text" field', () => {
		const workflow = {
			'1': {
				class_type: 'OtherPrompt',
				inputs: { text: 'hello world' },
				_meta: { title: 'Prompt' }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.inputs).toHaveLength(1);
		expect(result.inputs[0].key).toBe('1.text');
		expect(result.inputs[0].default).toBe('hello world');
	});

	it('includes repeat group inputs for Power Lora Loader (lora_1, lora_2, etc.)', () => {
		const workflow = {
			'162': {
				class_type: 'Power Lora Loader (rgthree)',
				inputs: {
					lora_1: { on: true, lora: 'loraA.safetensors', strength: 0.8 },
					lora_2: { on: false, lora: 'loraB.safetensors', strength: 1 }
				},
				_meta: { title: 'Power_Lora' }
			}
		};

		const result = analyzeWorkflow(workflow);

		const loraInputs = result.inputs.filter((i) => i.nodeId === '162' && i.groupKey);
		expect(loraInputs.length).toBeGreaterThan(0);

		const onInput = result.inputs.find((i) => i.key === '162.lora_1.on');
		const loraSelect = result.inputs.find((i) => i.key === '162.lora_1.lora');
		const strengthInput = result.inputs.find((i) => i.key === '162.lora_1.strength');
		expect(onInput).toBeDefined();
		expect(onInput?.type).toBe('boolean');
		expect(loraSelect).toBeDefined();
		expect(loraSelect?.default).toBe('loraA');
		expect(strengthInput).toBeDefined();
		expect(strengthInput?.default).toBe(0.8);
		expect(strengthInput?.min).toBe(0);
		expect(strengthInput?.max).toBe(2);

		const bindingsForLora1 = result.bindings.filter((b) => b.key.startsWith('162.lora_1.'));
		expect(bindingsForLora1.length).toBe(3);
	});

	it('includes fixed inputs for LoraLoader (lora_name, strength_model, strength_clip)', () => {
		const workflow = {
			'10': {
				class_type: 'LoraLoader',
				inputs: { lora_name: 'foo.safetensors', strength_model: 0.8, strength_clip: 1 },
				_meta: { title: 'LoRA' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '10.lora_name')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '10.strength_model')?.default).toBe(0.8);
		expect(result.inputs.find((i) => i.key === '10.strength_clip')?.default).toBe(1);
	});

	it('includes fixed inputs for LycorisLoaderNode including lycoris_type', () => {
		const workflow = {
			'20': {
				class_type: 'LycorisLoaderNode',
				inputs: { lora_name: 'bar.safetensors', strength_model: 1, strength_clip: 0.5, lycoris_type: 'LoHA' },
				_meta: { title: 'LyCORIS' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '20.lora_name')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '20.lycoris_type')?.default).toBe('LoHA');
	});

	it('detects SaveAudioMP3 as audio output', () => {
		const workflow = {
			'50': {
				class_type: 'SaveAudioMP3',
				inputs: { filename_prefix: 'out', quality: 'V0' },
				_meta: { title: 'Save Audio' }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.outputs).toHaveLength(1);
		expect(result.outputs[0]).toEqual({
			nodeId: '50',
			type: 'audio',
			label: 'Save Audio',
			metaTitle: 'Save Audio'
		});
	});

	it('assigns incremental image labels for multiple LoadImage nodes', () => {
		const workflow = {
			'1': { class_type: 'LoadImage', inputs: { image: 'image1.png' }, _meta: { title: 'Load Image 1' } },
			'2': { class_type: 'LoadImage', inputs: { image: 'image2.png' }, _meta: { title: 'Load Image 2' } }
		};

		const result = analyzeWorkflow(workflow);

		const imageInputs = result.inputs.filter((i) => i.type === 'image');
		expect(imageInputs.length).toBe(2);
		expect(imageInputs[0].label).toMatch(/Image 1$/);
		expect(imageInputs[1].label).toMatch(/Image 2$/);
	});

	it('detects VAEDecode as internal node (no input or output fields)', () => {
		const workflow = {
			'17': {
				class_type: 'VAEDecode',
				inputs: { samples: ['11', 0], vae: ['12', 2] },
				_meta: { title: 'VAE Decode' }
			}
		};

		const result = analyzeWorkflow(workflow);

		expect(result.outputs).toHaveLength(0);
		expect(result.internalNodes).toBeDefined();
		expect(result.internalNodes).toHaveLength(1);
		expect(result.internalNodes![0]).toEqual({ classType: 'VAEDecode', label: 'VAE Decode' });
	});

	it('uses layout row/col from spec when present', () => {
		const workflow = {
			'9': {
				class_type: 'KSampler',
				inputs: { seed: 1, steps: 20, cfg: 7.5, sampler_name: 'euler' }
			}
		};

		const result = analyzeWorkflow(workflow);

		const seedInput = result.inputs.find((i) => i.field === 'seed');
		expect(seedInput).toBeDefined();
		expect(seedInput).toHaveProperty('layoutRow');
		expect(seedInput).toHaveProperty('layoutCol');
	});
});

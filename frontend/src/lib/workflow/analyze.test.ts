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
		expect(textInput?.multiline).toBe(true);
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

	it('includes CheckpointLoader ckpt_name with optionSource checkpoints', () => {
		const workflow = {
			'1': { class_type: 'CheckpointLoader', inputs: { ckpt_name: 'model.safetensors' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '1.ckpt_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('checkpoints');
	});

	it('includes DiffusionModelLoader unet_name and weight_dtype', () => {
		const workflow = {
			'2': {
				class_type: 'DiffusionModelLoader',
				inputs: { unet_name: 'flux.safetensors', weight_dtype: 'fp16' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '2.unet_name')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '2.weight_dtype')?.default).toBe('fp16');
	});

	it('includes LoadDiffusionModel unet_name and weight_dtype', () => {
		const workflow = {
			'3': {
				class_type: 'LoadDiffusionModel',
				inputs: { unet_name: 'wan.safetensors', weight_dtype: 'default' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '3.unet_name')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '3.weight_dtype')).toBeDefined();
	});

	it('includes StableCascadeCheckpointLoader key_opt_b, key_opt_c, cache_mode with correct optionSources', () => {
		const workflow = {
			'4': {
				class_type: 'StableCascadeCheckpointLoader',
				inputs: {
					key_opt_b: 'stage_b.safetensors',
					key_opt_c: 'stage_c.safetensors',
					cache_mode: 'all'
				}
			}
		};
		const result = analyzeWorkflow(workflow);
		const bInp = result.inputs.find((i) => i.key === '4.key_opt_b');
		const cInp = result.inputs.find((i) => i.key === '4.key_opt_c');
		expect(bInp).toBeDefined();
		expect(cInp).toBeDefined();
		expect(bInp?.optionSource).toBe('stable_cascade_stage_b');
		expect(cInp?.optionSource).toBe('stable_cascade_stage_c');
		expect(result.inputs.find((i) => i.key === '4.cache_mode')?.default).toBe('all');
	});

	it('includes StableCascade_CheckpointLoader (Inspire alias) inputs', () => {
		const workflow = {
			'5': {
				class_type: 'StableCascade_CheckpointLoader',
				inputs: { key_opt_b: 'b.safetensors', key_opt_c: 'c.safetensors', cache_mode: 'none' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '5.key_opt_b')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '5.key_opt_c')).toBeDefined();
	});

	it('includes SD3CheckpointLoader ckpt_name and shift', () => {
		const workflow = {
			'6': {
				class_type: 'SD3CheckpointLoader',
				inputs: { ckpt_name: 'sd3_medium.safetensors', shift: 3 }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '6.ckpt_name')?.optionSource).toBe('checkpoints');
		expect(result.inputs.find((i) => i.key === '6.shift')?.default).toBe(3);
	});

	it('includes SD3LoadCheckpoint (alias) ckpt_name and shift', () => {
		const workflow = {
			'7': { class_type: 'SD3LoadCheckpoint', inputs: { ckpt_name: 'sd3.safetensors', shift: 6 } }
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '7.ckpt_name')).toBeDefined();
		expect(result.inputs.find((i) => i.key === '7.shift')?.default).toBe(6);
	});

	it('includes FluxCheckpointLoader ckpt_name with optionSource checkpoints', () => {
		const workflow = {
			'8': { class_type: 'FluxCheckpointLoader', inputs: { ckpt_name: 'flux1.safetensors' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '8.ckpt_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('checkpoints');
	});

	it('includes UpscaleModelLoader model_name with optionSource upscale_models', () => {
		const workflow = {
			'30': { class_type: 'UpscaleModelLoader', inputs: { model_name: '4x-UltraSharp.pth' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '30.model_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('upscale_models');
	});

	it('includes ESRGANLoader model_name with optionSource upscale_models', () => {
		const workflow = {
			'31': { class_type: 'ESRGANLoader', inputs: { model_name: 'BSRGAN.pth' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '31.model_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('upscale_models');
	});

	it('includes RealESRGANLoader and SwinIRLoader model_name with optionSource upscale_models', () => {
		const workflow = {
			'32': { class_type: 'RealESRGANLoader', inputs: { model_name: 'RealESRGAN_x4plus.pth' } },
			'33': { class_type: 'SwinIRLoader', inputs: { model_name: 'SwinIR-L.pth' } }
		};
		const result = analyzeWorkflow(workflow);
		const realInp = result.inputs.find((i) => i.key === '32.model_name');
		const swinInp = result.inputs.find((i) => i.key === '33.model_name');
		expect(realInp).toBeDefined();
		expect(realInp?.optionSource).toBe('upscale_models');
		expect(swinInp).toBeDefined();
		expect(swinInp?.optionSource).toBe('upscale_models');
	});

	it('includes ImageScale, ImageScaleBy and LatentUpscaleBy upscale_method with optionSource upscale_methods', () => {
		const workflow = {
			'40': { class_type: 'ImageScale', inputs: { upscale_method: 'lanczos', width: 512, height: 512 } },
			'42': { class_type: 'ImageScaleBy', inputs: { upscale_method: 'bicubic', scale_by: 2 } },
			'41': { class_type: 'LatentUpscaleBy', inputs: { upscale_method: 'bilinear', scale_by: 2 } }
		};
		const result = analyzeWorkflow(workflow);
		const imageScaleInp = result.inputs.find((i) => i.key === '40.upscale_method');
		const imageScaleByInp = result.inputs.find((i) => i.key === '42.upscale_method');
		const latentInp = result.inputs.find((i) => i.key === '41.upscale_method');
		expect(imageScaleInp).toBeDefined();
		expect(imageScaleInp?.optionSource).toBe('upscale_methods');
		expect(imageScaleByInp).toBeDefined();
		expect(imageScaleByInp?.optionSource).toBe('upscale_methods');
		expect(latentInp).toBeDefined();
		expect(latentInp?.optionSource).toBe('upscale_methods');
	});

	it('includes DualCLIPLoader clip_name1, clip_name2, type, device with correct optionSources', () => {
		const workflow = {
			'9': {
				class_type: 'DualCLIPLoader',
				inputs: { clip_name1: 'clip_l.safetensors', clip_name2: 'clip_g.safetensors', type: 'sdxl', device: 'default' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '9.clip_name1')?.optionSource).toBe('clip_models');
		expect(result.inputs.find((i) => i.key === '9.clip_name2')?.optionSource).toBe('clip_models');
		expect(result.inputs.find((i) => i.key === '9.type')?.optionSource).toBe('clip_types');
		expect(result.inputs.find((i) => i.key === '9.device')?.optionSource).toBe('devices');
	});

	it('includes TripleCLIPLoader clip_name1, clip_name2, clip_name3 with optionSource clip_models', () => {
		const workflow = {
			'10': {
				class_type: 'TripleCLIPLoader',
				inputs: { clip_name1: 'a.safetensors', clip_name2: 'b.safetensors', clip_name3: 'c.safetensors', type: 'flux', device: 'default' }
			}
		};
		const result = analyzeWorkflow(workflow);
		expect(result.inputs.find((i) => i.key === '10.clip_name1')?.optionSource).toBe('clip_models');
		expect(result.inputs.find((i) => i.key === '10.clip_name3')?.optionSource).toBe('clip_models');
	});

	it('includes CLIPVisionLoader clip_name with optionSource clip_vision_models', () => {
		const workflow = {
			'11': { class_type: 'CLIPVisionLoader', inputs: { clip_name: 'CLIP-ViT-H-14.safetensors' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '11.clip_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('clip_vision_models');
	});

	it('includes T5Loader t5_name with optionSource clip_models', () => {
		const workflow = {
			'12': { class_type: 'T5Loader', inputs: { t5_name: 't5xxl_fp16.safetensors' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '12.t5_name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('clip_models');
	});

	it('includes TextEncoderLoader name with optionSource clip_models', () => {
		const workflow = {
			'13': { class_type: 'TextEncoderLoader', inputs: { name: 'encoder.safetensors' } }
		};
		const result = analyzeWorkflow(workflow);
		const inp = result.inputs.find((i) => i.key === '13.name');
		expect(inp).toBeDefined();
		expect(inp?.optionSource).toBe('clip_models');
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

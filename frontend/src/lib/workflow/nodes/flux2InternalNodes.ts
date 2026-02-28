import type { NodeSpec } from '../types';

function internalSpec(classType: string): NodeSpec {
    return { classType, fixedInputs: {} };
}

export const SamplerCustomAdvancedSpec: NodeSpec = internalSpec('SamplerCustomAdvanced');
export const CFGGuiderSpec: NodeSpec = internalSpec('CFGGuider');
export const ConditioningZeroOutSpec: NodeSpec = internalSpec('ConditioningZeroOut');
export const GetImageSizeSpec: NodeSpec = internalSpec('GetImageSize');
export const ReferenceLatentSpec: NodeSpec = internalSpec('ReferenceLatent');
export const VAEEncodeSpec: NodeSpec = internalSpec('VAEEncode');
export const ImageUpscaleWithModelSpec: NodeSpec = internalSpec('ImageUpscaleWithModel');
export const AnySwitchRgthreeSpec: NodeSpec = internalSpec('Any Switch (rgthree)');
export const T5TokenizerOptionsSpec: NodeSpec = internalSpec('T5TokenizerOptions');

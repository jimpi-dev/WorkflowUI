import type { NodeSpec } from '../types';

export const CLIPVisionLoaderSpec: NodeSpec = {
    classType: 'CLIPVisionLoader',
    optionSourceForSelect: 'clip_vision_models',
    fixedInputs: {
        clip_name: {
            type: 'select',
            label: 'CLIP Vision model',
            optionSource: 'clip_vision_models'
        }
    }
};

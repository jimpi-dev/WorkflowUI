import type { NodeSpec } from '../types';

export const ImageScaleBySpec: NodeSpec = {
    classType: 'ImageScaleBy',
    fixedInputs: {
        scale_by: {
            type: 'number',
            label: 'Scale by',
            min: 0.01,
            max: 4,
            step: 0.01,
            slider: true
        }
    }
};

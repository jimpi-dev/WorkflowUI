import type { NodeSpec } from '../types';

export const ImageScaleSpec: NodeSpec = {
    classType: 'ImageScale',
    fixedInputs: {
        upscale_method: {
            type: 'select',
            label: 'Upscale method',
            optionSource: 'upscale_methods'
        },
        width: {
            type: 'number',
            label: 'Width',
            min: 64,
            max: 8192,
            step: 8
        },
        height: {
            type: 'number',
            label: 'Height',
            min: 64,
            max: 8192,
            step: 8
        },
        crop: {
            type: 'select',
            label: 'Crop',
            options: ['disabled', 'center', 'top', 'bottom', 'left', 'right']
        }
    }
};

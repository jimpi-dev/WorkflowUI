import type { NodeSpec } from '../types';

export const ImageScaleToTotalPixelsSpec: NodeSpec = {
    classType: 'ImageScaleToTotalPixels',
    fixedInputs: {
        upscale_method: {
            type: 'select',
            label: 'Upscale method',
            options: ['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos']
        },
        megapixels: {
            type: 'number',
            label: 'Megapixels',
            min: 0.1,
            max: 100,
            step: 0.1
        },
        resolution_steps: {
            type: 'number',
            label: 'Resolution steps',
            min: 1,
            max: 16
        },
        image: {
            type: 'image',
            label: 'Image'
        }
    }
};

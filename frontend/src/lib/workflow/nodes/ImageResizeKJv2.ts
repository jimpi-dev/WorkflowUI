import type { NodeSpec } from '../types';

export const ImageResizeKJv2Spec: NodeSpec = {
    classType: 'ImageResizeKJv2',
    fixedInputs: {
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
        upscale_method: {
            type: 'select',
            label: 'Upscale method',
            options: ['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos']
        },
        keep_proportion: {
            type: 'select',
            label: 'Keep proportion',
            options: ['resize', 'crop', 'pad']
        },
        pad_color: {
            type: 'text',
            label: 'Pad color'
        },
        crop_position: {
            type: 'select',
            label: 'Crop position',
            options: ['center', 'top', 'bottom', 'left', 'right']
        },
        divisible_by: {
            type: 'number',
            label: 'Divisible by',
            min: 1,
            max: 64,
            step: 1
        },
        device: {
            type: 'select',
            label: 'Device',
            optionSource: 'devices'
        },
        image: {
            type: 'image',
            label: 'Image'
        }
    }
};

import type { NodeSpec } from '../types';

export const VAEEncodeTiledSpec: NodeSpec = {
    classType: 'VAEEncodeTiled',
    fixedInputs: {
        tile_size: {
            type: 'number',
            label: 'Tile size',
            min: 64,
            max: 2048,
            step: 8
        },
        overlap: {
            type: 'number',
            label: 'Overlap',
            min: 0,
            max: 512
        },
        temporal_size: {
            type: 'number',
            label: 'Temporal size',
            min: 1,
            max: 256
        },
        temporal_overlap: {
            type: 'number',
            label: 'Temporal overlap',
            min: 0,
            max: 128
        }
    }
};

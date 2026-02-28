import { createLatentSizeSpec } from './latentSizeBase';

export const SDXLEmptyLatentSizePickerSpec = createLatentSizeSpec('SDXLEmptyLatentSizePicker+', {
    widthField: 'width_override',
    heightField: 'height_override',
    headerBadge: 'LATENT'
});

export const PowerLoraLoaderSpec: NodeSpec = {
    classType: 'Power Lora Loader (rgthree)',
    template: 'lora-stack',
    headerBadge: 'LORA',
    repeatGroups: [
        {
            match: /^lora_\d+$/,
            label: 'LoRAs',

            layout: {
                rows: [
                    ['on', 'lora'],
                    ['strength']
                ]
            },
            
            allowAdd: true,
            fields: {
                on: {
                    type: 'boolean',
                    label: 'Enabled',
                    hideLabel: true
                },
                lora: {
                    type: 'select',
                    label: 'LoRA',
                    readonly: true,
                    hideLabel: true
                },
                strength: {
                    type: 'number',
                    label: 'Strength',
                    min: 0,
                    max: 2,
                    step: 0.05,
                    slider: true
                }
            }
        }
    ]
};

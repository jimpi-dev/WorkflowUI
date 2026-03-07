export type InputType =
    | 'text'
    | 'number'
    | 'seed'
    | 'select'
    | 'image'
    | 'video'
    | 'audio'
    | 'boolean';

export type WorkflowInputRole =
    | 'seed'
    | 'parameter';

export type WorkflowInput = {
    key: string;
    label: string;
    type: InputType;
    role?: WorkflowInputRole;
    default?: any;
    nodeId: string;
    field: string;
    name?: string;
    min?: number;
    max?: number;
    options?: string[];
    optionSource?: string;
    layoutRow?: number;
    layoutCol?: number;
    classType: string;
    groupKey?: string;
    verticalAlign?: 'start' | 'center';
    metaTitle?: string | null;
};

export type WorkflowBinding = {
    key: string;
    nodeId: string;
    field: string;
};

export type WorkflowOutput = {
    nodeId: string;
    type: 'image' | 'video' | 'audio';
    label?: string;
    metaTitle?: string | null;
    outputIndex?: number;
    outputName?: string;
};

export type WorkflowModel = {
    inputs: WorkflowInput[];
    outputs: WorkflowOutput[];
    bindings: WorkflowBinding[];
    internalNodes?: { classType: string; label: string }[];
    template?: 'default' | 'lora-stack' | 'latent-resolution';
    masterSeedInputKey?: string;
    form_label?: string;
};

export type NodeInputSpec = {
    type: InputType;
    label?: string;
    min?: number;
    max?: number;
    step?: number;
    options?: string[];
    optionSource?: string;
    slider?: boolean;
};

export type NodeLayoutRow = string[];

export type NodeLayoutSpec = {
    rows: NodeLayoutRow[];
};

export type NodeSpec = {
    classType: string;
    fixedInputs: Record<string, NodeInputSpec>;
    repeatGroups?: RepeatGroupSpec[];
    layout?: NodeLayoutSpec;
    template?: 'default' | 'lora-stack' | 'latent-resolution';
    headerBadge?: string;
    outputs?: {
        type: 'image' | 'video' | 'audio';
    };
    optionSourceForSelect?: 'clip_models' | 'clip_vision_models';
};

export type UINode = {
    nodeId: string;
    classType: string;
    fixedFields: UIField[];
    repeatGroups: UIRepeatGroup[];
};

export type UIField = {
    key: string;
    value: any;
    spec: FieldSpec;
};

export type UIRepeatGroup = {
    label: string;
    instances: UIRepeatInstance[];
    allowAdd?: boolean;
};

export type UIRepeatInstance = {
    key: string;
    fields: UIField[];
};

export type FieldSpec = {
    type: 'boolean' | 'number' | 'select';
    label: string;
    min?: number;
    max?: number;
    step?: number;
    optionSource?: string;
    hideLabel?: boolean;
};

export type RepeatGroupSpec = {
    match: RegExp;
    label: string;
    allowAdd?: boolean;
    fields: Record<string, FieldSpec>;
};


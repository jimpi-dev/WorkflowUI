export type ComboDropdownBodyApi = {
    mount: (opts: {
        left: number;
        top: number;
        width: number;
        maxHeight: number;
        items: string[];
        onSelect: (path: string) => void;
        onClose: () => void;
    }) => void;
    update: (items: string[]) => void;
    setPosition: (left: number, top: number, width: number, maxHeight: number) => void;
    unmount: () => void;
};

const defaultEmptyMessage = 'No LoRAs match.';
const defaultFormatLabel = (path: string) =>
    path.split('/').pop()?.replace(/\.safetensors$/i, '') ?? path;

function createComboDropdownBody(options: {
    listboxId: string;
    ariaLabel: string;
    emptyMessage?: string;
    formatLabel?: (path: string) => string;
}): ComboDropdownBodyApi {
    const {
        listboxId,
        ariaLabel,
        emptyMessage = defaultEmptyMessage,
        formatLabel = defaultFormatLabel
    } = options;
    let root: HTMLDivElement | null = null;
    let onSelectRef: ((path: string) => void) | null = null;

    const baseStyle =
        'position: fixed; z-index: 2147483647; overflow-y: auto; background: var(--card); color: var(--text); border: 3px solid var(--accent); border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); font-family: inherit;';

    function handleClickOutside(e: MouseEvent) {
        if (root && !root.contains(e.target as Node)) {
            (root as any).__onClose?.();
        }
    }

    function escapeHtml(s: string): string {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function renderItems(
        container: HTMLDivElement,
        items: string[],
        onSelect: (path: string) => void
    ) {
        container.textContent = '';
        if (items.length === 0) {
            const empty = document.createElement('div');
            empty.style.cssText =
                'padding: 0.75rem; font-size: 0.85rem; color: var(--muted);';
            empty.textContent = emptyMessage;
            container.appendChild(empty);
            return;
        }
        for (const path of items) {
            const opt = document.createElement('div');
            opt.setAttribute('role', 'option');
            opt.style.cssText =
                'padding: 0.4rem 0.75rem; font-size: 0.85rem; cursor: pointer; display: flex; flex-direction: column; gap: 0.15rem; color: inherit;';
            const label = formatLabel(path);
            opt.innerHTML = `<span>${escapeHtml(label)}</span><span style="font-size: 0.7rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(path)}</span>`;
            opt.onmouseenter = () => {
                opt.style.background = 'var(--accent-soft)';
            };
            opt.onmouseleave = () => {
                opt.style.background = 'transparent';
            };
            opt.onmousedown = (e) => e.preventDefault();
            opt.onclick = () => onSelect(path);
            container.appendChild(opt);
        }
    }

    return {
        mount(opts) {
            if (root) this.unmount();
            onSelectRef = opts.onSelect;
            root = document.createElement('div');
            root.id = listboxId;
            (root as any).__onClose = opts.onClose;
            root.setAttribute('role', 'listbox');
            root.setAttribute('aria-label', ariaLabel);
            root.style.cssText = `${baseStyle} left: ${opts.left}px; top: ${opts.top}px; min-width: ${opts.width}px; max-height: ${opts.maxHeight}px;`;
            renderItems(root, opts.items, opts.onSelect);
            document.body.appendChild(root);
            setTimeout(() =>
                document.addEventListener('click', handleClickOutside),
                0
            );
        },
        update(items) {
            if (!root || !onSelectRef) return;
            renderItems(root, items, onSelectRef);
        },
        setPosition(left, top, width, maxHeight) {
            if (root)
                root.style.cssText = `${baseStyle} left: ${left}px; top: ${top}px; min-width: ${width}px; max-height: ${maxHeight}px;`;
        },
        unmount() {
            document.removeEventListener('click', handleClickOutside);
            if (root?.parentNode) root.parentNode.removeChild(root);
            root = null;
            onSelectRef = null;
        }
    };
}

export function createLoraDropdownBody(): ComboDropdownBodyApi {
    return createComboDropdownBody({
        listboxId: 'lora-combo-listbox',
        ariaLabel: 'LoRA list',
        emptyMessage: 'No LoRAs match.',
        formatLabel: (path) =>
            path.split('/').pop()?.replace(/\.safetensors$/i, '') ?? path
    });
}

export function createCheckpointDropdownBody(): ComboDropdownBodyApi {
    return createComboDropdownBody({
        listboxId: 'checkpoint-combo-listbox',
        ariaLabel: 'Checkpoint list',
        emptyMessage: 'No checkpoints match.',
        formatLabel: (path) =>
            path.split('/').pop()?.replace(/\.(safetensors|ckpt)$/i, '') ?? path
    });
}

export function createClipDropdownBody(): ComboDropdownBodyApi {
    return createComboDropdownBody({
        listboxId: 'clip-combo-listbox',
        ariaLabel: 'CLIP model list',
        emptyMessage: 'No CLIP models match.',
        formatLabel: (path) =>
            path.split('/').pop()?.replace(/\.(safetensors|ckpt|bin)$/i, '') ?? path
    });
}

export function createVaeDropdownBody(): ComboDropdownBodyApi {
    return createComboDropdownBody({
        listboxId: 'vae-combo-listbox',
        ariaLabel: 'VAE list',
        emptyMessage: 'No VAEs match.',
        formatLabel: (path) =>
            path.split('/').pop()?.replace(/\.(safetensors|ckpt|bin)$/i, '') ?? path
    });
}

export function createWorkflowDropdownBody(getLabel: (id: string) => string): ComboDropdownBodyApi {
    return createComboDropdownBody({
        listboxId: 'workflow-combo-listbox',
        ariaLabel: 'Workflow list',
        emptyMessage: 'No workflows match.',
        formatLabel: getLabel
    });
}

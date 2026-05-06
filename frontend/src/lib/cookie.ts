const COOKIE_PATH = '/';
const MAX_AGE_ONE_YEAR = 365 * 24 * 60 * 60;

export function getCookie(name: string): string | null {
    if (typeof document === 'undefined') return null;
    const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
}

export function setCookie(name: string, value: string, maxAgeSeconds: number = MAX_AGE_ONE_YEAR): void {
    if (typeof document === 'undefined') return;
    document.cookie = `${name}=${encodeURIComponent(value)}; path=${COOKIE_PATH}; max-age=${maxAgeSeconds}; SameSite=Lax`;
}

export const THUMB_SIZE_COOKIE = 'workflowui_thumb_size';

export const THUMB_SCALE_MIN = 25;
export const THUMB_SCALE_MAX = 300;
export const THUMB_SCALE_DEFAULT = 100;
export type ThumbFitMode = 'cover' | 'contain';

const VALID_THUMB_FIT_MODES: ThumbFitMode[] = ['cover', 'contain'];
const LEGACY_THUMB_SIZE_TO_SCALE: Record<string, number> = {
    small: 75,
    medium: THUMB_SCALE_DEFAULT,
    large: 125
};

function clampThumbScale(value: number): number {
    if (!Number.isFinite(value)) return THUMB_SCALE_DEFAULT;
    return Math.min(THUMB_SCALE_MAX, Math.max(THUMB_SCALE_MIN, Math.round(value)));
}

export function getThumbSizeCookie(): number {
    const raw = getCookie(THUMB_SIZE_COOKIE);
    if (!raw) return THUMB_SCALE_DEFAULT;
    if (Object.prototype.hasOwnProperty.call(LEGACY_THUMB_SIZE_TO_SCALE, raw)) {
        return LEGACY_THUMB_SIZE_TO_SCALE[raw];
    }
    const parsed = Number.parseInt(raw, 10);
    return clampThumbScale(parsed);
}

export function setThumbSizeCookie(sizePercent: number): void {
    setCookie(THUMB_SIZE_COOKIE, String(clampThumbScale(sizePercent)));
}

export const THUMB_FIT_MODE_COOKIE = 'workflowui_thumb_fit_mode';

export function getThumbFitModeCookie(): ThumbFitMode {
    const raw = getCookie(THUMB_FIT_MODE_COOKIE);
    if (raw && VALID_THUMB_FIT_MODES.includes(raw as ThumbFitMode)) return raw as ThumbFitMode;
    return 'cover';
}

export function setThumbFitModeCookie(mode: ThumbFitMode): void {
    setCookie(THUMB_FIT_MODE_COOKIE, mode);
}

export const THUMB_SHOW_FILENAME_COOKIE = 'workflowui_thumb_show_filename';

export const VAULT_SORT_COOKIE = 'workflowui_vault_sort';
export type VaultSortMode = 'recent' | 'usage';

export function getVaultSortCookie(): VaultSortMode {
    const raw = getCookie(VAULT_SORT_COOKIE);
    if (raw === 'usage' || raw === 'recent') return raw;
    return 'recent';
}

export function setVaultSortCookie(mode: VaultSortMode): void {
    setCookie(VAULT_SORT_COOKIE, mode);
}

export function getThumbShowFilenameCookie(): boolean {
    const raw = getCookie(THUMB_SHOW_FILENAME_COOKIE);
    return raw === '1' || raw === 'true';
}

export function setThumbShowFilenameCookie(show: boolean): void {
    setCookie(THUMB_SHOW_FILENAME_COOKIE, show ? '1' : '0');
}

export const NOTES_COLLAPSED_COOKIE = 'workflowui_notes_collapsed';

export function getNotesCollapsedCookie(): boolean {
    const raw = getCookie(NOTES_COLLAPSED_COOKIE);
    return raw === '1' || raw === 'true';
}

export function setNotesCollapsedCookie(collapsed: boolean): void {
    setCookie(NOTES_COLLAPSED_COOKIE, collapsed ? '1' : '0');
}

export const LEFT_PANEL_COLLAPSED_COOKIE = 'workflowui_left_panel_collapsed';

export function getLeftPanelCollapsedCookie(): boolean {
    const raw = getCookie(LEFT_PANEL_COLLAPSED_COOKIE);
    return raw === '1' || raw === 'true';
}

export function setLeftPanelCollapsedCookie(collapsed: boolean): void {
    setCookie(LEFT_PANEL_COLLAPSED_COOKIE, collapsed ? '1' : '0');
}

const SKIP_DELETE_CONFIRM_PREFIX = 'workflowui_skip_confirm_';

export const DELETE_CONFIRM_KEYS = {
    delete_remote: SKIP_DELETE_CONFIRM_PREFIX + 'delete_remote',
    delete_local: SKIP_DELETE_CONFIRM_PREFIX + 'delete_local',
    delete_all: SKIP_DELETE_CONFIRM_PREFIX + 'delete_all',
    delete_run: SKIP_DELETE_CONFIRM_PREFIX + 'delete_run',
} as const;

export type DeleteConfirmKey = keyof typeof DELETE_CONFIRM_KEYS;

export function getSkipDeleteConfirmCookie(action: DeleteConfirmKey): boolean {
    const raw = getCookie(DELETE_CONFIRM_KEYS[action]);
    return raw === '1' || raw === 'true';
}

export function setSkipDeleteConfirmCookie(action: DeleteConfirmKey, skip: boolean): void {
    setCookie(DELETE_CONFIRM_KEYS[action], skip ? '1' : '0');
}

export const QUEUE_GROUPS_COLLAPSED_COOKIE = 'workflowui_queue_groups_collapsed';

export function getQueueGroupsCollapsedCookie(): boolean {
    const raw = getCookie(QUEUE_GROUPS_COLLAPSED_COOKIE);
    return raw === '1' || raw === 'true';
}

export function setQueueGroupsCollapsedCookie(collapsed: boolean): void {
    setCookie(QUEUE_GROUPS_COLLAPSED_COOKIE, collapsed ? '1' : '0');
}

const QUEUE_PANEL_WIDTH_COOKIE = 'workflowui_queue_panel_width';
const QUEUE_PANEL_WIDTH_DEFAULT = 380;
const QUEUE_PANEL_WIDTH_MIN = 280;

export function getQueuePanelWidthCookie(): number {
    const raw = getCookie(QUEUE_PANEL_WIDTH_COOKIE);
    if (raw === null || raw === '') return QUEUE_PANEL_WIDTH_DEFAULT;
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n < QUEUE_PANEL_WIDTH_MIN) return QUEUE_PANEL_WIDTH_DEFAULT;
    return n;
}

export function setQueuePanelWidthCookie(width: number): void {
    const w = Math.max(QUEUE_PANEL_WIDTH_MIN, Math.round(width));
    setCookie(QUEUE_PANEL_WIDTH_COOKIE, String(w));
}

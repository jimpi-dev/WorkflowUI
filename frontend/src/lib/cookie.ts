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

export type ThumbSize = 'small' | 'medium' | 'large';

const VALID_THUMB_SIZES: ThumbSize[] = ['small', 'medium', 'large'];

export function getThumbSizeCookie(): ThumbSize {
    const raw = getCookie(THUMB_SIZE_COOKIE);
    if (raw && VALID_THUMB_SIZES.includes(raw as ThumbSize)) return raw as ThumbSize;
    return 'medium';
}

export function setThumbSizeCookie(size: ThumbSize): void {
    setCookie(THUMB_SIZE_COOKIE, size);
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
} as const;

export type DeleteConfirmKey = keyof typeof DELETE_CONFIRM_KEYS;

export function getSkipDeleteConfirmCookie(action: DeleteConfirmKey): boolean {
    const raw = getCookie(DELETE_CONFIRM_KEYS[action]);
    return raw === '1' || raw === 'true';
}

export function setSkipDeleteConfirmCookie(action: DeleteConfirmKey, skip: boolean): void {
    setCookie(DELETE_CONFIRM_KEYS[action], skip ? '1' : '0');
}

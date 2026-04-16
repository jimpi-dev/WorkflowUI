import { writable } from 'svelte/store';

export type AuthUser = {
  id: string;
  username: string;
  role: 'admin' | 'user';
  allow_all_apps: boolean;
};

export type AuthState = {
  enabled: boolean;
  authenticated: boolean;
  user: AuthUser | null;
  loaded: boolean;
};

export const authState = writable<AuthState>({
  enabled: false,
  authenticated: false,
  user: null,
  loaded: false
});

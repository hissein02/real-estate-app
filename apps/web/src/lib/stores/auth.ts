import { writable, derived } from 'svelte/store';
import type { User, CompanyInfoData } from '$lib/api/types';

export const currentUser = writable<User | null>(null);
export const isAuthenticated = derived(currentUser, ($user) => $user !== null);

export function setUser(user: User | null) {
	currentUser.set(user);
}

export const companyInfo = writable<CompanyInfoData | null>(null);

export function setCompanyInfo(info: CompanyInfoData | null) {
	companyInfo.set(info);
}

import type { User } from '$lib/api/types';

declare global {
	namespace App {
		interface Locals {
			user: User | null;
		}
		interface PageData {
			user?: User | null;
		}
	}
}

export {};

import type { Config } from 'tailwindcss';

export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				primary: {
					50:  '#f0f7fb',
					100: '#c8e0f4',  // Pale Sky
					200: '#9dd1f1',  // Baby Blue
					300: '#6bb4de',
					400: '#508aa8',  // Air Force Blue
					500: '#3d7290',
					600: '#2d5a73',
					700: '#1e4059',
					800: '#122d41',
					900: '#031927',  // Ink Black
					950: '#02111c',
				}
			}
		}
	},
	plugins: []
} satisfies Config;

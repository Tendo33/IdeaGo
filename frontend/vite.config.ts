import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
	plugins: [
		react(),
		tailwindcss(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	build: {
		rollupOptions: {
			output: {
				manualChunks(id) {
					if (!id.includes("node_modules")) {
						return undefined
					}

					if (
						id.includes("node_modules/react/") ||
						id.includes("node_modules/react-dom/")
					) {
						return "react-vendor"
					}

					if (id.includes("node_modules/react-router")) {
						return "router-vendor"
					}

					if (
						id.includes("node_modules/i18next") ||
						id.includes("node_modules/react-i18next")
					) {
						return "i18n-vendor"
					}

					if (
						id.includes("node_modules/@supabase/") ||
						id.includes("node_modules/@sentry/")
					) {
						return "service-vendor"
					}

					if (id.includes("node_modules/recharts")) {
						return "recharts"
					}

					if (id.includes("node_modules/framer-motion")) {
						return "framer-motion"
					}

					if (
						id.includes("node_modules/sonner") ||
						id.includes("node_modules/lucide-react")
					) {
						return "ui-vendor"
					}

					return undefined
				},
			},
		},
	},
	server: {
		proxy: {
			"/api": {
				target: "http://localhost:8000",
				changeOrigin: true,
			},
		},
	},
});

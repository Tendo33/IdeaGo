import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
	plugins: [
		react(),
		tailwindcss(),
		// Serve empty runtime config in dev so /env-config.js never 404s
		{
			name: "dev-env-config",
			configureServer(server) {
				server.middlewares.use("/env-config.js", (_req, res) => {
					res.setHeader("Content-Type", "application/javascript");
					res.end('window.__APP_CONFIG__ = { apiKey: "" };');
				});
			},
		},
	],
	build: {
		rollupOptions: {
			output: {
				manualChunks: {
					recharts: ["recharts"],
					"framer-motion": ["framer-motion"],
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

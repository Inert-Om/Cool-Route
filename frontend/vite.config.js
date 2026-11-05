import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Frontend calls /api/... and Vite forwards it to Flask (no CORS headaches)
    proxy: { "/api": "http://localhost:5000" },
  },
});

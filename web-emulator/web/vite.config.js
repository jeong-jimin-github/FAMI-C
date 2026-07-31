import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    exclude: ["jsnes"],
  },
  server: {
    port: 3000,
    open: true,
    watch: {
      // Watch the core jsnes source for changes
      ignored: ["!**/node_modules/jsnes/**"],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.js"],
  },
});

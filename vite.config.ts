import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({ base:'./', plugins: [react(), tailwindcss()], server: {port:1424, strictPort:true, watch:{ignored:['**/src-tauri/target/**','**/dist/**','**/docs/**']}, proxy:{'/api':{target:'http://127.0.0.1:1425',changeOrigin:true,configure(proxy){proxy.on('proxyReq',request=>request.setHeader('Origin','http://127.0.0.1:1424'));}}}}, clearScreen:false, build:{chunkSizeWarningLimit:3500,rollupOptions:{output:{manualChunks(id){if(id.includes('/node_modules/')&&id.includes('molstar'))return 'molecular-engine';}}}} });

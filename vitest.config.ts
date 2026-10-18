import {defineConfig} from 'vitest/config';

// Transform Mol*'s browser ESM for the real parser/bond graph regression checks.
export default defineConfig({test:{server:{deps:{inline:['molstar']}}}});

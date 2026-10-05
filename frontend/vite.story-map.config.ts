import { defineConfig, mergeConfig } from 'vite';
import { fixtureConfig } from './vite.fixture.config';

export default defineConfig(() => mergeConfig(
  fixtureConfig(process.env.JIPPEEL_FIXTURE_API_VIOLATIONS ?? ''),
  { cacheDir: 'node_modules/.vite-story-map' },
));

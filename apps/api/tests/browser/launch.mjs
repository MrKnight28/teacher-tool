// One place that starts the browser for every browser check.
// Default: the installed Microsoft Edge. Set BROWSER_PATH to the path of any Chromium
// build to use that instead (for example on a machine without Edge). Nothing else changes.
import { chromium } from 'playwright-core';

const ARGS = ['--autoplay-policy=no-user-gesture-required', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'];

export function launch() {
  const exe = process.env.BROWSER_PATH;
  const opts = { headless: true, args: ARGS };
  if (exe) opts.executablePath = exe; else opts.channel = 'msedge';
  return chromium.launch(opts);
}

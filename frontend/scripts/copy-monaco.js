/**
 * Copies monaco-editor pre-built files to public/ for runtime loading.
 * This avoids bundling Monaco via Rollup (which causes OOM on constrained systems).
 * Monaco loads at runtime from /monaco-editor/vs/* — CSP 'self' compliant.
 */
import { cpSync, existsSync, mkdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const src = resolve(__dirname, '../node_modules/monaco-editor/min')
const dest = resolve(__dirname, '../public/monaco-editor')

if (!existsSync(src)) {
  console.warn('[copy-monaco] monaco-editor not found in node_modules — skipping')
  process.exit(0)
}

mkdirSync(dest, { recursive: true })
cpSync(src, dest, { recursive: true, force: true })
console.log('[copy-monaco] Copied monaco-editor/min → public/monaco-editor/')

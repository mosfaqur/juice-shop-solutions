#!/usr/bin/env node
/**
 * Solve every find-it / fix-it coding challenge from a pinned Juice Shop
 * source tree.
 *
 * Replicates lib/codingChallenges.ts from juice-shop v20.2.0 exactly:
 *   - walks the same SNIPPET_PATHS,
 *   - extracts each `vuln-code-snippet` challenge key,
 *   - recomputes vulnLines/neutralLines with getCodingChallengeFromFileContent()
 *     (markers are stripped from the served snippet, so line numbers must be
 *     recomputed locally from the markers — this is why the source tree is
 *     required),
 *   - POSTs /snippets/verdict with exactly vulnLines (find it),
 *   - brute-forces selectedFix 0..N-1 against /snippets/fixes (fix it).
 *
 * Usage:
 *   node coding_challenge_solver.mjs --base URL [--source ./juice-shop] [--cookie C] [--dry-run]
 */

import fs from 'node:fs/promises'
import path from 'node:path'

const SNIPPET_PATHS = Object.freeze([
  './server.ts', './routes', './lib', './data',
  './data/static/web3-snippets', './frontend/src/app',
  './models', './infrastructure'
])

function args () {
  const a = process.argv.slice(2)
  const get = (name) => {
    const i = a.indexOf(name)
    return i >= 0 ? a[i + 1] : undefined
  }
  return {
    base: get('--base'),
    source: get('--source') ?? './juice-shop',
    cookie: get('--cookie') ?? '',
    dryRun: a.includes('--dry-run')
  }
}

async function findFilesWithCodeChallenges (base, currPath) {
  const matches = []
  const abs = path.join(base, currPath)
  try {
    const st = await fs.lstat(abs)
    if (st.isDirectory()) {
      const files = await fs.readdir(abs)
      for (const file of files) {
        const sub = await findFilesWithCodeChallenges(base, path.join(currPath, file))
        matches.push(...sub)
      }
    } else {
      const code = await fs.readFile(abs, 'utf8')
      if (code.includes('// vuln-code' + '-snippet start') || code.includes('# vuln-code' + '-snippet start')) {
        matches.push({ path: currPath, content: code })
      }
    }
  } catch {
    console.warn(`[!] could not read ${currPath}`)
  }
  return matches
}

function getCodingChallengeFromFileContent (source, challengeKey) {
  const snippets = source.match(`[/#]{0,2} vuln-code-snippet start.*${challengeKey}([^])*vuln-code-snippet end.*${challengeKey}`)
  if (snippets == null) {
    throw new Error('Broken code snippet boundaries for: ' + challengeKey)
  }
  let snippet = snippets[0]
  snippet = snippet.replace(/\s?[/#]{0,2} vuln-code-snippet start.*[\r\n]{0,2}/g, '')
  snippet = snippet.replace(/\s?[/#]{0,2} vuln-code-snippet end.*/g, '')
  snippet = snippet.replace(/.*[/#]{0,2} vuln-code-snippet hide-line[\r\n]{0,2}/g, '')
  snippet = snippet.replace(/.*[/#]{0,2} vuln-code-snippet hide-start([^])*[/#]{0,2} vuln-code-snippet hide-end[\r\n]{0,2}/g, '')
  snippet = snippet.trim()

  let lines = snippet.split('\r\n')
  if (lines.length === 1) lines = snippet.split('\n')
  if (lines.length === 1) lines = snippet.split('\r')
  const vulnLines = []
  const neutralLines = []
  for (let i = 0; i < lines.length; i++) {
    if (new RegExp(`vuln-code-snippet vuln-line.*${challengeKey}`).exec(lines[i]) != null) {
      vulnLines.push(i + 1)
    } else if (new RegExp(`vuln-code-snippet neutral-line.*${challengeKey}`).exec(lines[i]) != null) {
      neutralLines.push(i + 1)
    }
  }
  return { challengeKey, vulnLines, neutralLines }
}

function getCodeChallengesFromFile (file) {
  const challengeKeyRegex = /[/#]{0,2} vuln-code-snippet start (?<challenges>.*)/g
  const challenges = [...file.content.matchAll(challengeKeyRegex)]
    .flatMap((m) => m.groups?.challenges?.split(' ') ?? [])
    .filter(Boolean)
  return challenges.map((key) => getCodingChallengeFromFileContent(file.content, key))
}

async function computeChallenges (source) {
  const map = new Map()
  for (const p of SNIPPET_PATHS) {
    const files = await findFilesWithCodeChallenges(source, p)
    for (const file of files) {
      for (const cc of getCodeChallengesFromFile(file)) {
        map.set(cc.challengeKey, cc)
      }
    }
  }
  return map
}

async function main () {
  const { base, source, cookie, dryRun } = args()
  const challenges = await computeChallenges(source)
  console.log(`[*] computed ${challenges.size} code challenges from ${source}`)

  if (!base || dryRun) {
    for (const [key, cc] of challenges) {
      console.log(`${key}: vulnLines=${JSON.stringify(cc.vulnLines)} neutralLines=${JSON.stringify(cc.neutralLines)}`)
    }
    console.log('[dry-run] no requests sent')
    return
  }

  const headers = { 'Content-Type': 'application/json' }
  if (cookie) headers.Cookie = cookie
  const j = (method, url, body) =>
    fetch(`${base}${url}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    }).then(async (r) => ({ status: r.status, json: await r.json().catch(() => null) }))

  let solvedFindIt = 0
  let solvedFixIt = 0
  for (const [key, cc] of challenges) {
    const v = await j('POST', '/snippets/verdict', { key, selectedLines: cc.vulnLines })
    if (v.json?.verdict) {
      solvedFindIt++
    }
    let fixIndex = -1
    const fixes = await j('GET', `/snippets/fixes/${key}`)
    const n = fixes.json?.fixes?.length ?? 0
    for (let i = 0; i < n; i++) {
      const f = await j('POST', '/snippets/fixes', { key, selectedFix: i })
      if (f.json?.verdict) {
        fixIndex = i
        solvedFixIt++
        break
      }
    }
    console.log(`${key}: find-it=${v.json?.verdict ?? v.status} fix-it=${fixIndex >= 0 ? `ok(idx ${fixIndex})` : v.json?.verdict ? 'pending' : 'failed'}`)
  }
  console.log(`\n[*] done: find-it ${solvedFindIt}/${challenges.size}, fix-it ${solvedFixIt}/${challenges.size}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})

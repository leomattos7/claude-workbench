// Pure helpers for the session board: no Claude Code calls, so they can be tested alone.

export const WARN_AT = 65
export const REARM_BELOW = 50
export const STALE_MS = 2 * 60 * 60 * 1000
export const FUTURE_SKEW_MS = 60 * 1000
export const KEY_PREFIX = 's:'

// Store values are data, not trusted text: strip control, invisible and bidi characters and cap the length.
function isUnsafeCodePoint(c) {
  return (
    c < 0x20 || c === 0x7f || (c >= 0x80 && c <= 0x9f) || c === 0xad || c === 0x61c ||
    (c >= 0x200b && c <= 0x200f) || (c >= 0x2028 && c <= 0x202e) || (c >= 0x2060 && c <= 0x2064) ||
    (c >= 0x2066 && c <= 0x2069) || c === 0xfeff || (c >= 0xe0000 && c <= 0xe007f)
  )
}

export function clean(value, max = 120) {
  const chars = Array.from(String(value ?? ''), (ch) => (isUnsafeCodePoint(ch.codePointAt(0)) ? '?' : ch))
  return chars.slice(0, max).join('')
}

// Shape check for what another session may have written: a session id, a model name, an absolute path.
export function isValidEntry(entry) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return false
  if (typeof entry.id !== 'string' || !/^[0-9a-f-]{8,64}$/i.test(entry.id)) return false
  if (typeof entry.model !== 'string' || !/^[\w.\-\[\]@:]{1,64}$/.test(entry.model)) return false
  if (typeof entry.cwd !== 'string' || !/^([A-Za-z]:[\\/]|\/)/.test(entry.cwd)) return false
  return true
}

export function isStale(entry, now) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return true
  if (typeof entry.updatedAt !== 'number' || !Number.isFinite(entry.updatedAt)) return true
  return entry.updatedAt > now + FUTURE_SKEW_MS || now - entry.updatedAt > STALE_MS
}

// One-time warning: fires when the fill reaches WARN_AT, re-arms after it drops below REARM_BELOW (compaction, /clear).
export function nextWarnState(percent, warned) {
  if (typeof percent !== 'number' || !Number.isFinite(percent)) return { warn: false, warned }
  if (percent < REARM_BELOW) return { warn: false, warned: false }
  if (percent >= WARN_AT && !warned) return { warn: true, warned: true }
  return { warn: false, warned }
}

export function warnText(percent) {
  return `Context at ${Math.round(percent)}%: consider starting a fresh session with a handoff note.`
}

export function formatBoard(entries, selfId) {
  if (entries.length === 0) return 'No sessions registered.'
  const lines = entries
    .slice()
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .map((s) => {
      const ctx = typeof s.percent === 'number' && Number.isFinite(s.percent) ? `${String(Math.round(s.percent)).padStart(3)}%` : '  - '
      const self = s.id === selfId ? '  (this one)' : ''
      return `  ${clean(s.id, 8)}  ctx ${ctx}  ${clean(s.model, 40)}  ${clean(s.cwd)}${self}`
    })
  return [
    `Sessions open on this machine (${entries.length}):`,
    ...lines,
    'To message another session, ask Claude and use /list-agents (cross-session messaging is built in).',
  ].join('\n')
}

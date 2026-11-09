import { KEY_PREFIX, formatBoard, isStale, isValidEntry, nextWarnState, warnText } from './board.js'

// The session that ended last, so a measurement still in flight for it cannot republish it.
// The block lasts seconds only: a session resumed later with --resume must publish again.
const RACE_WINDOW_MS = 5000
let lastEnded = { id: undefined, at: 0 }

export function register(on) {
  let warned = false

  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: 'board',
        description: 'List the Claude Code sessions open on this machine (context, model, folder).',
      })
    } catch {
      // The command is a convenience; the session must start regardless.
    }
    return next(e)
  })

  // Runs after each turn, when the context fill moved: publish this session and warn once near the limit.
  on('session.measure', async ($, e, next) => {
    try {
      const percent = e.context?.percent
      const state = nextWarnState(percent, warned)
      warned = state.warned
      if (state.warn) $.ui.toast(warnText(percent), { timeoutMs: 10000 })

      const cwd = await $.session.cwd()
      const model = await $.session.model()
      const updatedAt = await $.clock.now()
      const id = await $.session.id()
      if (!(id === lastEnded.id && updatedAt - lastEnded.at < RACE_WINDOW_MS)) {
        await $.store.set(KEY_PREFIX + id, {
          id,
          cwd,
          model,
          percent: typeof percent === 'number' && Number.isFinite(percent) ? percent : null,
          updatedAt,
        })
      }
    } catch {
      // Observability only: never get in the way of the turn.
    }
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    try {
      // The event names the session that is ending; after /clear or --resume this process lives on under a new id.
      const id = e.sessionId ?? (await $.session.id())
      lastEnded = { id, at: await $.clock.now() }
      await $.store.delete(KEY_PREFIX + id)
    } catch {
      // A leftover entry is dropped as stale by /board.
    }
    return next(e)
  })

  on('command.run', { command: 'board' }, async ($) => {
    const now = await $.clock.now()
    const entries = []
    for (const key of await $.store.keys()) {
      if (!key.startsWith(KEY_PREFIX)) continue
      const entry = await $.store.get(key)
      if (isStale(entry, now) || !isValidEntry(entry)) {
        await $.store.delete(key)
        continue
      }
      entries.push(entry)
    }
    return { text: formatBoard(entries, await $.session.id()) }
  })
}

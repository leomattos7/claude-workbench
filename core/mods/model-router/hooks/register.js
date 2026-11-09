import { decide } from './route.js'

// WORKBENCH_MODEL_ROUTER=observe shows what would change without changing it (read once per process).
export function register(on) {
  let mode

  on('agent.spawn', async ($, e, next) => {
    let d
    try {
      if (mode === undefined) {
        mode = (await $.env.get('WORKBENCH_MODEL_ROUTER')) === 'observe' ? 'observe' : 'enforce'
      }
      d = decide({ subagentType: e.subagentType, model: e.model, fork: e.fork, parentModel: e.parentModel })
    } catch {
      return next(e)
    }
    if (!d.changed) return next(e)

    // A failed toast must not drop the cap, so it never sits between the decision and next().
    try {
      const label = `${e.subagentType}: ${e.model ?? 'default'} -> ${d.model}`
      $.ui.toast(mode === 'observe' ? `model-router (observe) ${label}` : `model-router ${label}`)
    } catch {
      // Informational only.
    }
    return mode === 'observe' ? next(e) : next({ ...e, model: d.model })
  })
}

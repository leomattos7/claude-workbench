// Pure routing policy: no Claude Code calls, so it can be unit tested alone.

export const RANK = { haiku: 1, sonnet: 2, opus: 3, fable: 4 }

// Per subagent type: the highest model it may run on (`ceiling`).
// A type that is not listed is left alone (architect, critic, planner, security-reviewer,
// code-reviewer, analyst, general-purpose, Plan, other plugins' agents, ...).
export const POLICY = new Map([
  ['explore', { ceiling: 'sonnet' }],
  ['writer', { ceiling: 'sonnet' }],
  ['executor', { ceiling: 'sonnet' }],
  ['debugger', { ceiling: 'sonnet' }],
  ['test-engineer', { ceiling: 'sonnet' }],
  ['qa-tester', { ceiling: 'sonnet' }],
  ['designer', { ceiling: 'sonnet' }],
  ['tracer', { ceiling: 'sonnet' }],
  ['git-master', { ceiling: 'sonnet' }],
  ['scientist', { ceiling: 'sonnet' }],
  ['verifier', { ceiling: 'sonnet' }],
])

// Only built-in names (no prefix) and these plugin prefixes are matched; any other "plugin:agent" is left alone.
const PLUGIN_PREFIXES = ['oh-my-claudecode:']

export function rankOf(model) {
  const m = String(model ?? '').toLowerCase()
  for (const [name, rank] of Object.entries(RANK)) if (m.includes(name)) return rank
  return undefined
}

// "oh-my-claudecode:Executor" -> "executor"; "Explore" -> "explore"; "foo:executor" -> undefined
export function typeKey(subagentType) {
  const t = String(subagentType ?? '').toLowerCase()
  const prefix = PLUGIN_PREFIXES.find((p) => t.startsWith(p))
  if (prefix) return t.slice(prefix.length)
  return t.includes(':') ? undefined : t
}

// Never raises a model above what would otherwise have run, only lowers it to the type's ceiling.
// A fork inherits its parent's model and ignores `model`, so it passes through untouched.
export function decide({ subagentType, model, fork, parentModel }) {
  if (fork) return { model, changed: false, reason: 'fork' }
  const key = typeKey(subagentType)
  const policy = key === undefined ? undefined : POLICY.get(key)
  if (!policy) return { model, changed: false, reason: 'unlisted' }

  const ceiling = RANK[policy.ceiling]
  const isNamed = !(model == null || model === '' || model === 'inherit')

  if (isNamed) {
    const rank = rankOf(model)
    if (rank === undefined) return { model, changed: false, reason: 'unknown model' }
    if (rank > ceiling) return { model: policy.ceiling, changed: true, reason: 'capped' }
    return { model, changed: false, reason: 'within tier' }
  }
  if (model === 'inherit') {
    const rank = rankOf(parentModel)
    if (rank === undefined) return { model, changed: false, reason: 'unknown parent model' }
    if (rank > ceiling) return { model: policy.ceiling, changed: true, reason: 'capped parent model' }
    return { model, changed: false, reason: 'within tier' }
  }
  // No model named: the agent definition decides, and the router leaves it alone.
  return { model, changed: false, reason: 'agent default' }
}

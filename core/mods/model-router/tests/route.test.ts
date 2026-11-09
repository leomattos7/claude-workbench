import { expect, test } from 'claude-code/testing'
import { POLICY, RANK, decide, rankOf, typeKey } from '../hooks/route.js'

const OMC = 'oh-my-claudecode:'

test('typeKey drops only known plugin prefixes and lowercases', () => {
  expect(typeKey(`${OMC}Executor`)).toBe('executor')
  expect(typeKey('Explore')).toBe('explore')
  expect(typeKey('foo:executor')).toBeUndefined()
})

test('rankOf reads aliases and full ids', () => {
  expect(rankOf('haiku')).toBe(1)
  expect(rankOf('claude-sonnet-5-5')).toBe(2)
  expect(rankOf('claude-opus-5-5')).toBe(3)
  expect(rankOf('something-else')).toBeUndefined()
})

test('caps a model above the type ceiling', () => {
  expect(decide({ subagentType: `${OMC}executor`, model: 'opus', fork: false })).toMatchObject({ model: 'sonnet', changed: true })
})

test('Explore keeps the sonnet the planner asked for and is capped only above it', () => {
  expect(decide({ subagentType: 'Explore', model: 'sonnet', fork: false })).toMatchObject({ model: 'sonnet', changed: false })
  expect(decide({ subagentType: 'Explore', model: 'haiku', fork: false })).toMatchObject({ model: 'haiku', changed: false })
  expect(decide({ subagentType: 'Explore', model: 'opus', fork: false })).toMatchObject({ model: 'sonnet', changed: true })
  expect(decide({ subagentType: `${OMC}writer`, model: 'opus', fork: false })).toMatchObject({ model: 'sonnet', changed: true })
})

test('keeps a cheaper model the planner asked for', () => {
  expect(decide({ subagentType: `${OMC}executor`, model: 'haiku', fork: false })).toMatchObject({ model: 'haiku', changed: false })
})

test('with no model named the agent definition decides', () => {
  for (const type of ['Explore', `${OMC}executor`, `${OMC}verifier`, `${OMC}document-specialist`]) {
    expect(decide({ subagentType: type, fork: false })).toMatchObject({ changed: false })
  }
})

test('inherit is judged by the parent model and is never raised', () => {
  expect(decide({ subagentType: `${OMC}executor`, model: 'inherit', fork: false, parentModel: 'claude-opus-5-5' })).toMatchObject({ model: 'sonnet', changed: true })
  expect(decide({ subagentType: `${OMC}executor`, model: 'inherit', fork: false, parentModel: 'claude-haiku-5-5' })).toMatchObject({ model: 'inherit', changed: false })
  expect(decide({ subagentType: `${OMC}executor`, model: 'inherit', fork: false, parentModel: 'mystery' })).toMatchObject({ changed: false })
})

test('never returns a model above the one that would have run', () => {
  const parents = ['claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5']
  for (const [key, policy] of POLICY) {
    for (const asked of [undefined, 'inherit', 'haiku', 'sonnet', 'opus']) {
      for (const parentModel of parents) {
        const d = decide({ subagentType: `${OMC}${key}`, model: asked, fork: false, parentModel })
        if (asked === undefined) {
          expect(d.changed).toBe(false)
          continue
        }
        // What would have run without the router: the named model, or the parent's for inherit.
        const baseline = asked === 'inherit' ? rankOf(parentModel)! : rankOf(asked)!
        const result = d.changed ? rankOf(d.model)! : baseline
        expect(result).toBeLessThanOrEqual(baseline)
        if (d.changed) expect(rankOf(d.model)!).toBeLessThanOrEqual(RANK[policy.ceiling as keyof typeof RANK])
      }
    }
  }
})

test('leaves analysis agents, unlisted types and other plugins alone', () => {
  for (const t of [`${OMC}document-specialist`, `${OMC}architect`, `${OMC}critic`, `${OMC}planner`, `${OMC}security-reviewer`, 'general-purpose', 'Plan', 'foo:executor', 'foo:designer']) {
    expect(decide({ subagentType: t, model: 'opus', fork: false })).toMatchObject({ model: 'opus', changed: false })
  }
})

test('object property names are not treated as agent types', () => {
  for (const t of ['constructor', '__proto__', 'toString', `${OMC}constructor`, `${OMC}__proto__`]) {
    expect(decide({ subagentType: t, fork: false })).toMatchObject({ changed: false })
  }
})

test('a fork passes through even with inherit under an opus parent', () => {
  const d = decide({ subagentType: `${OMC}executor`, model: 'inherit', fork: true, parentModel: 'claude-opus-5-5' })
  expect(d).toMatchObject({ changed: false, reason: 'fork' })
})

test('passes forks and unknown model ids through', () => {
  expect(decide({ subagentType: `${OMC}executor`, model: 'opus', fork: true }).changed).toBe(false)
  expect(decide({ subagentType: `${OMC}executor`, model: 'weird-model', fork: false }).changed).toBe(false)
})

function spawnStubs(on: any, seen: unknown[], env: string | undefined, toast: () => unknown) {
  on('env.get', () => ({ value: env }))
  on('ui.toast', toast)
  on('agent.spawn', ($: any, e: any) => {
    seen.push(e.model)
    return { model: String(e.model), agentId: 'a1' }
  })
}

test('the hook rewrites the model that reaches the spawn and says so', async ($, on) => {
  const seen: unknown[] = []
  const toasts: string[] = []
  spawnStubs(on, seen, undefined, ($: any, e: any) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  await $.agent.spawn({ prompt: 'task', subagentType: `${OMC}executor`, model: 'opus' })
  expect(seen).toEqual(['sonnet'])
  expect(toasts).toEqual([`model-router ${OMC}executor: opus -> sonnet`])
})

test('observe mode reports but does not change the model', async ($, on) => {
  const seen: unknown[] = []
  const toasts: string[] = []
  spawnStubs(on, seen, 'observe', ($: any, e: any) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  await $.agent.spawn({ prompt: 'task', subagentType: `${OMC}executor`, model: 'opus' })
  expect(seen).toEqual(['opus'])
  expect(toasts).toEqual([`model-router (observe) ${OMC}executor: opus -> sonnet`])
})

test('a failing env read lets the spawn through unchanged', async ($, on) => {
  const seen: unknown[] = []
  on('env.get', () => ({ deny: 'env broke' }))
  on('agent.spawn', ($: any, e: any) => {
    seen.push(e.model)
    return { model: String(e.model), agentId: 'a1' }
  })
  await $.agent.spawn({ prompt: 'task', subagentType: `${OMC}executor`, model: 'opus' })
  expect(seen).toEqual(['opus'])
})

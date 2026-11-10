import { describe, expect, it, vi } from 'vitest';
import { platformTools } from '../src/tools/platformTools.js';
import { OmertaClient } from '../src/omertaClient.js';
import { runTaskInput } from '../src/mcp/schemas.js';

describe('platformTools', () => {
  it('preserves task record defaults and arbitrary JSON under Zod 4', () => {
    expect(runTaskInput.parse({ agent_id: 'agent-a', intent: 'echo' }))
      .toEqual({ agent_id: 'agent-a', intent: 'echo', params: {} });
    const params = { nested: { values: [1, null, true] } };
    expect(runTaskInput.parse({ agent_id: 'agent-a', intent: 'echo', params }).params).toEqual(params);
    expect(runTaskInput.safeParse({ agent_id: 1, intent: 'echo' }).success).toBe(false);
    expect(runTaskInput.safeParse({ agent_id: 'agent-a', intent: 'echo', params: null }).success).toBe(false);
  });

  it('exposes expected names', () => {
    const dummy = { listAgents: vi.fn(), getAgent: vi.fn(), runTask: vi.fn(), getTaskStatus: vi.fn(), getHealth: vi.fn() } as unknown as OmertaClient;
    const tools = platformTools(dummy);
    const names = tools.map((t) => t.name);
    expect(names).toContain('omerta.list_agents');
    expect(names).toContain('omerta.run_task');
  });
});

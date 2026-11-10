import { z } from 'zod';

export const listAgentsOutput = z.object({ agents: z.array(z.object({ id: z.string(), name: z.string().optional() })) });

export const getAgentInput = z.object({ agent_id: z.string() });
export const runTaskInput = z.object({ agent_id: z.string(), intent: z.string(), params: z.record(z.string(), z.any()).default({}) });
export const taskStatusInput = z.object({ task_id: z.string() });

export type GetAgentInput = z.infer<typeof getAgentInput>;
export type RunTaskInput = z.infer<typeof runTaskInput>;
export type TaskStatusInput = z.infer<typeof taskStatusInput>;

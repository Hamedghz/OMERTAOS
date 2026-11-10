import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, vi, expect, beforeEach, afterEach } from 'vitest';
import { PolicyEditor } from '../../components/PolicyEditor';
import { reloadRouterPolicy, updatePolicy } from '../../lib/api';

vi.mock('../../lib/api', () => ({
  fetchPolicy: vi.fn().mockResolvedValue({
    budget: { default_usd: 0.02, hard_cap_usd: 0.2 },
    latency: { local: 600, api: 2000, hybrid: 2300 },
  }),
  updatePolicy: vi.fn().mockResolvedValue({ ok: true }),
  reloadRouterPolicy: vi.fn().mockResolvedValue({ ok: true }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe('PolicyEditor', () => {
  let client: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    client = new QueryClient();
  });

  afterEach(() => {
    cleanup();
    client.clear();
  });

  it('submits updated policy', async () => {
    render(
      <QueryClientProvider client={client}>
        <PolicyEditor />
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByDisplayValue('0.02')).toBeInTheDocument());

    const input = screen.getByLabelText('Budget default (USD)');
    fireEvent.change(input, { target: { value: '0.05' } });

    const saveButton = screen.getByText('save');
    fireEvent.click(saveButton);

    await waitFor(() => expect(updatePolicy).toHaveBeenCalledOnce());
    expect(vi.mocked(updatePolicy).mock.calls[0][0]).toEqual({
      budget: { default_usd: 0.05, hard_cap_usd: 0.2 },
      latency: { local: 600, api: 2000, hybrid: 2300 },
    });
    await waitFor(() => expect(reloadRouterPolicy).toHaveBeenCalledOnce());
  });

  it.each(['-1', ''])('does not send an invalid budget %j', async (value) => {
    render(
      <QueryClientProvider client={client}>
        <PolicyEditor />
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByDisplayValue('0.02')).toBeInTheDocument());
    const input = screen.getByLabelText('Budget default (USD)');
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByText('save'));
    await waitFor(() => expect(input.parentElement?.querySelector('p')).toHaveTextContent(/\S/));
    expect(updatePolicy).not.toHaveBeenCalled();
  });
});

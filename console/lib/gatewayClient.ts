import 'server-only';

import { cookies, headers } from 'next/headers';

import { GATEWAY_HTTP_URL } from '@/lib/gatewayConfig';
import { appendGatewayContextHeaders } from '@/lib/gatewayContext';
import { resolveEnvironment } from '@/lib/environment';

const DEFAULT_GATEWAY = 'http://localhost:3000';

export function resolveGatewayBase() {
  return GATEWAY_HTTP_URL || DEFAULT_GATEWAY;
}

export async function buildGatewayHeaders(initHeaders?: HeadersInit) {
  const result = new Headers(initHeaders ?? {});
  const hdrs = await headers();
  appendGatewayContextHeaders(result, hdrs);

  const token = (await cookies()).get('access_token')?.value;
  if (token && !result.has('authorization')) {
    result.set('authorization', `Bearer ${token}`);
  }

  const internalAdminToken = resolveEnvironment('OMERTA_GATEWAY_ADMIN_TOKEN', {
    aliases: ['AION_GATEWAY_ADMIN_TOKEN', 'AION_ADMIN_TOKEN'],
  });
  if (internalAdminToken && !result.has('x-aion-admin-token')) {
    result.set('x-aion-admin-token', internalAdminToken);
  }

  return result;
}

export async function gatewayFetch(path: string, init?: RequestInit) {
  const url = `${resolveGatewayBase()}${path}`;
  const headers = await buildGatewayHeaders(init?.headers);
  const response = await fetch(url, {
    ...init,
    headers,
    cache: init?.cache ?? 'no-store',
  });

  const text = await response.text();
  const isJson = (response.headers.get('content-type') || '').includes('application/json');
  const body = isJson ? safeJson(text) : text;

  if (!response.ok) {
    const error = new Error(`Gateway error ${response.status}`);
    (error as any).status = response.status;
    (error as any).body = body;
    throw error;
  }

  return body;
}

function safeJson(payload: string) {
  try {
    return JSON.parse(payload);
  } catch {
    return { raw: payload };
  }
}

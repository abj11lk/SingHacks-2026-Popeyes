import type { AgentRun } from "../types";
export type { AgentRun };

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options?.headers || {}),
        },
    });

    if (!res.ok) {
        let message = `Request failed (${res.status})`;
        try {
            const body = await res.json();
            if (body?.detail) message = body.detail;
        } catch {
            // Ignore parse errors
        }
        throw new Error(message);
    }

    return res.json();
}

// /api/rm/* doesn't exist on our backend at all -- every call here is meant to
// fall back to the real /api/clients/* route. An earlier version of this file
// only fell back when err.message contained "404", but FastAPI's default 404
// body is {"detail":"Not Found"} -- a message of "Not Found", not "404" -- so
// that check never matched and the fallback never ran. Falling back
// unconditionally (like getClientWorkspace in api/client.ts already does) is
// what actually reaches our backend.

export async function getAgentRun(
    clientId: string,
    agentType: string
): Promise<AgentRun> {
    const encodedClient = encodeURIComponent(clientId);
    const encodedType = encodeURIComponent(agentType);

    try {
        return await request<AgentRun>(
            `/api/rm/client/${encodedClient}/agent-runs/${encodedType}`
        );
    } catch {
        return await request<AgentRun>(
            `/api/clients/${encodedClient}/agent-runs/${encodedType}`
        );
    }
}

export async function generateAgentRun(
    clientId: string,
    agentType: string
): Promise<AgentRun> {
    const encodedClient = encodeURIComponent(clientId);
    const encodedType = encodeURIComponent(agentType);

    try {
        return await request<AgentRun>(
            `/api/rm/client/${encodedClient}/agent-runs/${encodedType}/generate`,
            { method: "POST" }
        );
    } catch {
        return await request<AgentRun>(
            `/api/clients/${encodedClient}/agent-runs/${encodedType}/generate`,
            { method: "POST" }
        );
    }
}

// Book-wide, not per-client -- the Prioritisation Agent's narrative
// briefing on top of the already-ranked, already-scored client list.
export function getPrioritiesRun(): Promise<AgentRun> {
    return request<AgentRun>("/api/priorities/agent-run");
}

export function generatePrioritiesRun(): Promise<AgentRun> {
    return request<AgentRun>("/api/priorities/agent-run/generate", { method: "POST" });
}
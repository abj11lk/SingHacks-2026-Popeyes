import type {
    Client,
    ClientWorkspace,
    Recommendation,
    AumTrend,
} from "../types";

const API_BASE =
    import.meta.env.VITE_API_URL ||
    "http://localhost:8000";

async function request<T>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const response = await fetch(
        `${API_BASE}${path}`,
        {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...(options?.headers || {}),
            },
        }
    );

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const body = await response.json();
            if (body.detail) {
                message = body.detail;
            }
        } catch {
            // Ignore JSON parsing failure.
        }
        throw new Error(message);
    }

    return response.json();
}

// ============================================================
// Workspace & Client Endpoints
//
// /api/rm/* is a namespace this branch's backend never implements (only
// /api/clients/* is real -- see backend/api.py). Every function below tries
// /api/rm first and falls back unconditionally on any failure, rather than
// string-matching the error (that approach silently broke agentClient.ts's
// equivalent calls -- see the comment there).
// ============================================================

export async function getClientWorkspace(
    clientId: string
): Promise<ClientWorkspace> {
    const encoded = encodeURIComponent(clientId);
    try {
        return await request<ClientWorkspace>(`/api/rm/client/${encoded}`);
    } catch {
        return await request<ClientWorkspace>(`/api/clients/${encoded}`);
    }
}

export async function getClients(): Promise<{
    as_of: string;
    clients: Client[];
    total: number;
}> {
    try {
        return await request<{ as_of: string; clients: Client[]; total: number }>(
            "/api/rm/clients"
        );
    } catch {
        const clients = await request<Client[]>("/api/clients");
        return { as_of: new Date().toISOString(), clients, total: clients.length };
    }
}

export async function getAumTrend(clientId: string): Promise<AumTrend> {
    return request<AumTrend>(`/api/clients/${encodeURIComponent(clientId)}/aum-trend`);
}

// ============================================================
// Recommendations
// ============================================================

export async function listRecommendations(
    clientId: string
): Promise<Recommendation[]> {
    const encoded = encodeURIComponent(clientId);
    try {
        return await request<Recommendation[]>(`/api/rm/client/${encoded}/recommendations`);
    } catch {
        return await request<Recommendation[]>(`/api/clients/${encoded}/recommendations`);
    }
}

export async function actOnRecommendation(
    recommendationId: string,
    action: "accepted" | "edited" | "rejected",
    opts?: { editedText?: string; note?: string }
): Promise<void> {
    const encoded = encodeURIComponent(recommendationId);
    const body = JSON.stringify({
        action,
        edited_text: opts?.editedText ?? null,
        note: opts?.note ?? null,
    });

    try {
        await request<void>(`/api/rm/recommendations/${encoded}/action`, { method: "POST", body });
    } catch {
        await request<void>(`/api/recommendations/${encoded}/actions`, { method: "POST", body });
    }
}

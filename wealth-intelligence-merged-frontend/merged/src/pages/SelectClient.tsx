import { Users } from "lucide-react";

// Landing state before any client is picked from the sidebar list.
export default function SelectClient() {
    return (
        <div className="page">
            <div className="empty-state" style={{ marginTop: "80px" }}>
                <Users size={28} style={{ marginBottom: "10px" }} />
                <p style={{ margin: 0 }}>Select a client from the list to view their workspace.</p>
            </div>
        </div>
    );
}

export function formatCurrency(
    value: number | string | null | undefined,
    currency: string = "USD"
): string {
    if (value === null || value === undefined || value === "") return "$0.00";
    const num = typeof value === "string" ? parseFloat(value) : value;
    if (isNaN(num)) return "$0.00";

    return new Intl.NumberFormat("en-SG", {
        style: "currency",
        currency: currency,
        maximumFractionDigits: 0,
        minimumFractionDigits: 0,
    }).format(num);
}

export function formatPercent(
    value: number | string | null | undefined,
    decimals: number = 1
): string {
    if (value === null || value === undefined || value === "") return "0.0%";
    const num = typeof value === "string" ? parseFloat(value) : value;
    if (isNaN(num)) return "0.0%";
    return `${num >= 0 ? "+" : ""}${num.toFixed(decimals)}%`;
}

export function formatBps(
    value: number | string | null | undefined
): string {
    if (value === null || value === undefined || value === "") return "0 bps";
    const num = typeof value === "string" ? parseFloat(value) : value;
    if (isNaN(num)) return "0 bps";
    return `${Math.round(num)} bps`;
}

const WEALTH_BAND_LABELS: Record<string, string> = {
    HNW: "High Net Worth",
    UHNW: "Ultra High Net Worth",
};

export function formatWealthBand(
    value?: string | null
): string {
    if (!value) return "";
    return WEALTH_BAND_LABELS[value] ?? value;
}

export function formatCompactNumber(
    value: number | string | null | undefined
): string {
    if (value === null || value === undefined) return "0";
    const num = typeof value === "string" ? parseFloat(value) : value;
    if (isNaN(num)) return "0";
    return new Intl.NumberFormat("en-SG", {
        notation: "compact",
        compactDisplay: "short",
    }).format(num);
}
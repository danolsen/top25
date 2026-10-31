export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function csrfToken(): string | null {
  const match = document.cookie.split("; ").find((row) => row.startsWith("csrf="));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

function errorMessage(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item)))
        .join(" ");
    }
  }
  return "Something went wrong.";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const method = (options.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD"].includes(method)) {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(data));
  return data as T;
}

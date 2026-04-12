const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_URL}/api`;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    if (res.status === 204) return {} as T;
    return res.json();
  }

  // Auth
  async login(username: string, password: string) {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return data;
  }

  async getMe() {
    return this.request<any>("/auth/me");
  }

  logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  }

  // Cameras
  async getCameras() {
    return this.request<any[]>("/cameras/");
  }

  async getCamera(id: string) {
    return this.request<any>(`/cameras/${id}`);
  }

  async createCamera(data: any) {
    return this.request<any>("/cameras/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateCamera(id: string, data: any) {
    return this.request<any>(`/cameras/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteCamera(id: string) {
    return this.request(`/cameras/${id}`, { method: "DELETE" });
  }

  // Events
  async getEvents(params?: Record<string, string>) {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request<any[]>(`/events/${query}`);
  }

  async getEvent(id: string) {
    return this.request<any>(`/events/${id}`);
  }

  async getEventStats(hours = 24) {
    return this.request<any>(`/events/stats?hours=${hours}`);
  }

  // Zones
  async getZones(cameraId?: string) {
    const query = cameraId ? `?camera_id=${cameraId}` : "";
    return this.request<any[]>(`/zones/${query}`);
  }

  // Recordings
  async getRecordings(params?: Record<string, string>) {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return this.request<any[]>(`/recordings/${query}`);
  }

  async getTimeline(cameraId: string, date?: string) {
    const query = date ? `?date=${date}` : "";
    return this.request<any>(`/recordings/timeline/${cameraId}${query}`);
  }

  // Alerts
  async getAlerts() {
    return this.request<any[]>("/alerts/");
  }

  async createAlert(data: any) {
    return this.request<any>("/alerts/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Health
  async getHealth() {
    return this.request<any>("/health/");
  }

  async getSystemHealth() {
    return this.request<any>("/health/system");
  }

  // Snapshots
  getSnapshotUrl(path: string): string {
    return `${this.baseUrl}/snapshots/${path}`;
  }

  async fetchSnapshot(path: string): Promise<Blob> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(this.getSnapshotUrl(path), { headers });
    if (!res.ok) throw new Error(`Failed to fetch snapshot: ${res.status}`);
    return res.blob();
  }

  // Assistant
  async askAssistant(question: string) {
    const res = await fetch(`${API_URL}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.getToken()}`,
      },
      body: JSON.stringify({ question }),
    });
    return res.json();
  }
}

export const api = new ApiClient();

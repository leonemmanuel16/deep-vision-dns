"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Camera,
  Bell,
  Users,
  Car,
  Activity,
  TrendingUp,
  AlertTriangle,
  Wifi,
} from "lucide-react";

interface Stats {
  total: number;
  by_type: Record<string, number>;
  by_label: Record<string, number>;
  by_camera: Record<string, number>;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cameras, setCameras] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [s, c, e] = await Promise.all([
          api.getEventStats(24),
          api.getCameras(),
          api.getEvents({ limit: "10" }),
        ]);
        setStats(s);
        setCameras(c);
        setEvents(e);
        setError(null);
      } catch (err: any) {
        console.error("Dashboard load error:", err);
        setError(
          err?.message || "No se pudo conectar con el servidor. Verifica que la API este en linea."
        );
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-text-muted">
          Cargando dashboard...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-surface border border-border rounded-xl">
        <AlertTriangle className="w-12 h-12 text-danger mb-4" />
        <h2 className="text-lg font-semibold text-text-primary mb-2">
          Error al cargar el dashboard
        </h2>
        <p className="text-text-muted text-sm text-center max-w-md">
          {error}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const onlineCameras = cameras.filter((c) => c.status === "online").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-muted text-sm mt-1">
            Resumen de actividad en tiempo real
          </p>
        </div>
        <div className="text-xs text-text-muted">
          Ultima actualizacion: {formatDate(new Date())}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Camera}
          label="Camaras"
          value={`${onlineCameras}/${cameras.length}`}
          sub="en linea"
          color="primary"
        />
        <StatCard
          icon={Bell}
          label="Eventos (24h)"
          value={stats?.total || 0}
          sub="detecciones"
          color="accent"
        />
        <StatCard
          icon={Users}
          label="Personas"
          value={stats?.by_label?.person || 0}
          sub="detectadas hoy"
          color="success"
        />
        <StatCard
          icon={Car}
          label="Vehiculos"
          value={
            (stats?.by_label?.car || 0) +
            (stats?.by_label?.truck || 0) +
            (stats?.by_label?.bus || 0)
          }
          sub="detectados hoy"
          color="warning"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Events */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
            <Bell className="w-4 h-4 text-accent" />
            Eventos Recientes
          </h2>
          <div className="space-y-2">
            {events.length === 0 ? (
              <p className="text-text-muted text-sm py-4 text-center">
                Sin eventos recientes
              </p>
            ) : (
              events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background hover:bg-surface-hover transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        event.label === "person"
                          ? "bg-success"
                          : event.label === "car"
                          ? "bg-warning"
                          : "bg-accent"
                      }`}
                    />
                    <div>
                      <p className="text-sm text-text-primary font-medium">
                        {event.label}
                      </p>
                      <p className="text-xs text-text-muted">
                        {event.event_type}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-text-secondary">
                      {Math.round(event.confidence * 100)}%
                    </p>
                    <p className="text-xs text-text-muted">
                      {formatDate(event.detected_at)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Cameras Status */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
            <Camera className="w-4 h-4 text-primary" />
            Estado de Camaras
          </h2>
          <div className="space-y-2">
            {cameras.length === 0 ? (
              <p className="text-text-muted text-sm py-4 text-center">
                Sin camaras configuradas
              </p>
            ) : (
              cameras.map((cam) => (
                <div
                  key={cam.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background hover:bg-surface-hover transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Wifi
                      className={`w-4 h-4 ${
                        cam.status === "online"
                          ? "text-success"
                          : "text-danger"
                      }`}
                    />
                    <div>
                      <p className="text-sm text-text-primary">{cam.name}</p>
                      <p className="text-xs text-text-muted">{cam.location}</p>
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      cam.status === "online"
                        ? "bg-success/10 text-success"
                        : "bg-danger/10 text-danger"
                    }`}
                  >
                    {cam.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Detections by Type */}
      {stats && Object.keys(stats.by_label).length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-accent" />
            Detecciones por Tipo (24h)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {Object.entries(stats.by_label).map(([label, count]) => (
              <div
                key={label}
                className="bg-background rounded-lg p-3 text-center"
              >
                <p className="text-lg font-bold text-text-primary">{count}</p>
                <p className="text-xs text-text-muted capitalize">{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: any;
  label: string;
  value: number | string;
  sub: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    primary: "bg-primary/10 text-primary",
    accent: "bg-accent/10 text-accent",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning",
    danger: "bg-danger/10 text-danger",
  };

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorMap[color]}`}
        >
          <Icon className="w-5 h-5" />
        </div>
        <span className="text-sm text-text-secondary">{label}</span>
      </div>
      <p className="text-2xl font-bold text-text-primary">{value}</p>
      <p className="text-xs text-text-muted mt-1">{sub}</p>
    </div>
  );
}

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
      } catch (err) {
        // DEV: load demo data when backend is unavailable
        setStats({
          total: 347,
          by_type: { person_detected: 189, vehicle_detected: 112, animal_detected: 46 },
          by_label: { person: 189, car: 78, truck: 23, bus: 11, dog: 28, cat: 18 },
          by_camera: {},
        });
        setCameras([
          { id: "cam-1", name: "Entrada Principal", location: "Lobby", status: "online", brand: "Hikvision", model: "DS-2CD2143", recording_enabled: true },
          { id: "cam-2", name: "Estacionamiento", location: "Exterior", status: "online", brand: "Dahua", model: "IPC-HFW2831", recording_enabled: true },
          { id: "cam-3", name: "Almacen", location: "Interior", status: "offline", brand: "Hikvision", model: "DS-2CD2043", recording_enabled: false },
          { id: "cam-4", name: "Acceso Peatonal", location: "Lateral", status: "online", brand: "Axis", model: "P3245-V", recording_enabled: true },
        ]);
        setEvents([
          { id: "e1", label: "person", event_type: "person_detected", confidence: 0.94, detected_at: new Date().toISOString() },
          { id: "e2", label: "car", event_type: "vehicle_detected", confidence: 0.87, detected_at: new Date(Date.now() - 300000).toISOString() },
          { id: "e3", label: "person", event_type: "person_detected", confidence: 0.91, detected_at: new Date(Date.now() - 600000).toISOString() },
          { id: "e4", label: "dog", event_type: "animal_detected", confidence: 0.82, detected_at: new Date(Date.now() - 900000).toISOString() },
          { id: "e5", label: "truck", event_type: "vehicle_detected", confidence: 0.89, detected_at: new Date(Date.now() - 1200000).toISOString() },
        ]);
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

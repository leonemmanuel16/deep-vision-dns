"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity, Cpu, HardDrive, MemoryStick, Gpu } from "lucide-react";

export default function HealthPage() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHealth();
    const interval = setInterval(loadHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadHealth() {
    try {
      const data = await api.getSystemHealth();
      setHealth(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  if (loading || !health) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-muted">Cargando sistema...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          Salud del Sistema
        </h1>
        <p className="text-text-muted text-sm mt-1">
          Monitor en tiempo real de recursos
        </p>
      </div>

      {/* Resource Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* CPU */}
        <ResourceCard
          icon={Cpu}
          label="CPU"
          value={`${health.cpu.percent}%`}
          sub={`${health.cpu.cores} cores`}
          percent={health.cpu.percent}
          color={health.cpu.percent > 80 ? "danger" : health.cpu.percent > 60 ? "warning" : "success"}
        />

        {/* Memory */}
        <ResourceCard
          icon={MemoryStick}
          label="Memoria RAM"
          value={`${health.memory.used_gb} GB`}
          sub={`de ${health.memory.total_gb} GB`}
          percent={health.memory.percent}
          color={health.memory.percent > 85 ? "danger" : health.memory.percent > 70 ? "warning" : "success"}
        />

        {/* Disk */}
        <ResourceCard
          icon={HardDrive}
          label="Disco"
          value={`${health.disk.used_gb} GB`}
          sub={`de ${health.disk.total_gb} GB`}
          percent={health.disk.percent}
          color={health.disk.percent > 90 ? "danger" : health.disk.percent > 75 ? "warning" : "success"}
        />

        {/* GPU */}
        <ResourceCard
          icon={Activity}
          label="GPU"
          value={
            health.gpu.available !== false
              ? `${health.gpu.utilization_percent}%`
              : "N/A"
          }
          sub={
            health.gpu.available !== false
              ? `${health.gpu.name} | ${health.gpu.temperature_c}°C`
              : "No disponible"
          }
          percent={health.gpu.utilization_percent || 0}
          color={
            health.gpu.available === false
              ? "muted"
              : health.gpu.utilization_percent > 90
              ? "danger"
              : "success"
          }
        />
      </div>

      {/* GPU Details */}
      {health.gpu.available !== false && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            GPU NVIDIA
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-text-muted">Modelo</p>
              <p className="text-sm text-text-primary">{health.gpu.name}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Temperatura</p>
              <p className="text-sm text-text-primary">{health.gpu.temperature_c}°C</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">VRAM Usada</p>
              <p className="text-sm text-text-primary">{health.gpu.memory_used_mb} MB</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">VRAM Total</p>
              <p className="text-sm text-text-primary">{health.gpu.memory_total_mb} MB</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ResourceCard({
  icon: Icon,
  label,
  value,
  sub,
  percent,
  color,
}: {
  icon: any;
  label: string;
  value: string;
  sub: string;
  percent: number;
  color: string;
}) {
  const colorMap: Record<string, { bar: string; text: string }> = {
    success: { bar: "bg-success", text: "text-success" },
    warning: { bar: "bg-warning", text: "text-warning" },
    danger: { bar: "bg-danger", text: "text-danger" },
    muted: { bar: "bg-muted", text: "text-muted" },
  };

  const c = colorMap[color] || colorMap.muted;

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <Icon className="w-5 h-5 text-text-secondary" />
        <span className="text-sm text-text-secondary">{label}</span>
      </div>
      <p className="text-2xl font-bold text-text-primary">{value}</p>
      <p className="text-xs text-text-muted mt-1">{sub}</p>
      <div className="mt-3 h-1.5 bg-background rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${c.bar}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}

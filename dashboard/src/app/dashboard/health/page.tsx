"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Zap,
  Thermometer,
  Fan,
  RefreshCw,
  Clock,
  Monitor,
  AlertTriangle,
  Trash2,
} from "lucide-react";

// ── Circular Gauge Component ───────────────────────────────
function CircularGauge({
  percent,
  color,
  icon: Icon,
  size = 140,
}: {
  percent: number;
  color: string;
  icon: any;
  size?: number;
}) {
  const r = (size - 16) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (Math.min(percent, 100) / 100) * circumference;

  const colorMap: Record<string, string> = {
    green: "#10b981",
    yellow: "#f59e0b",
    orange: "#f97316",
    red: "#ef4444",
    purple: "#a855f7",
    blue: "#3b82f6",
  };
  const strokeColor = colorMap[color] || colorMap.green;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="currentColor"
          className="text-gray-200 dark:text-gray-700"
          strokeWidth="8"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={strokeColor}
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <Icon className="w-4 h-4 text-gray-400 mb-1" />
        <span className="text-2xl font-bold" style={{ color: strokeColor }}>
          {Math.round(percent)}
          <span className="text-sm">%</span>
        </span>
      </div>
    </div>
  );
}

// ── Progress Bar Component ──────────────────────────────────
function ProgressBar({
  percent,
  color = "blue",
  height = "h-2.5",
}: {
  percent: number;
  color?: string;
  height?: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "bg-blue-500",
    green: "bg-emerald-500",
    yellow: "bg-yellow-500",
    orange: "bg-orange-500",
    red: "bg-red-500",
    purple: "bg-purple-500",
  };
  return (
    <div className={`w-full ${height} bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden`}>
      <div
        className={`${height} rounded-full transition-all duration-700 ease-out ${colorMap[color] || colorMap.blue}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}

// ── Helper: get color based on percent ──────────────────────
function getColor(pct: number, thresholds = { warn: 60, danger: 80 }) {
  if (pct >= thresholds.danger) return "red";
  if (pct >= thresholds.warn) return "orange";
  return "green";
}

// ── Main Page ───────────────────────────────────────────────
export default function HealthPage() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [interval, setRefreshInterval] = useState(5);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [alerts, setAlerts] = useState<string[]>([]);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadHealth = useCallback(async () => {
    try {
      const data = await api.getSystemHealth();
      setHealth(data);
      setLastUpdate(new Date());

      // Generate alerts
      const newAlerts: string[] = [];
      if (data.cpu?.percent > 90) newAlerts.push(`CPU al ${data.cpu.percent}% - Carga critica`);
      if (data.memory?.percent > 85) newAlerts.push(`RAM al ${data.memory.percent}% - Memoria alta`);
      if (data.disk?.percent > 90) newAlerts.push(`Disco al ${data.disk.percent}% - Espacio bajo`);
      if (data.gpu?.available && data.gpu.temperature_c > 85)
        newAlerts.push(`GPU a ${data.gpu.temperature_c}C - Temperatura alta`);
      if (data.gpu?.available && data.gpu.utilization_percent > 95)
        newAlerts.push(`GPU al ${data.gpu.utilization_percent}% - Carga maxima`);
      if (data.gpu?.available && data.gpu.memory_used_mb / data.gpu.memory_total_mb > 0.9)
        newAlerts.push(`VRAM al ${Math.round((data.gpu.memory_used_mb / data.gpu.memory_total_mb) * 100)}%`);
      if (data.swap?.percent > 50) newAlerts.push(`Swap al ${data.swap.percent}% - Memoria insuficiente`);
      if (data.cpu?.load_avg?.[0] > data.cpu.cores_logical * 2)
        newAlerts.push(`Load Average ${data.cpu.load_avg[0]} - Sistema sobrecargado`);
      setAlerts(newAlerts);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = globalThis.setInterval(loadHealth, interval * 1000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, interval, loadHealth]);

  if (loading || !health) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-gray-400">Cargando sistema...</div>
      </div>
    );
  }

  const gpu = health.gpu || {};
  const gpuAvailable = gpu.available !== false;
  const vramPercent = gpuAvailable && gpu.memory_total_mb > 0
    ? Math.round((gpu.memory_used_mb / gpu.memory_total_mb) * 100)
    : 0;
  const cpuColor = getColor(health.cpu.percent);
  const memColor = getColor(health.memory.percent, { warn: 70, danger: 85 });
  const gpuColor = gpuAvailable ? getColor(gpu.utilization_percent) : "purple";
  const diskColor = getColor(health.disk.percent, { warn: 75, danger: 90 });

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Salud del Sistema
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Status badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-full text-xs font-medium">
            <Activity className="w-3 h-3 animate-pulse" />
            Monitoreo activo
            <span className="bg-emerald-100 dark:bg-emerald-800 px-1.5 py-0.5 rounded text-[10px]">
              cada {interval}s
            </span>
          </div>

          {/* Uptime */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
            <Clock className="w-3 h-3" />
            Uptime: {health.uptime?.formatted || "N/A"}
          </div>

          {/* Divider */}
          <div className="h-6 w-px bg-gray-300 dark:bg-gray-600" />

          {/* Auto toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              autoRefresh
                ? "bg-emerald-500 text-white"
                : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
            }`}
          >
            {autoRefresh ? "Auto" : "Pausado"}
          </button>

          {/* Interval selector */}
          <div className="flex bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
            {[3, 5, 10].map((s) => (
              <button
                key={s}
                onClick={() => setRefreshInterval(s)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  interval === s
                    ? "bg-blue-500 text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                }`}
              >
                {s}s
              </button>
            ))}
          </div>

          {/* Manual refresh */}
          <button
            onClick={loadHealth}
            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── 4 Gauge Cards ── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {/* CPU */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col items-center">
          <CircularGauge percent={health.cpu.percent} color={cpuColor} icon={Cpu} />
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-3">CPU</h3>
          <p className="text-[11px] text-gray-400">
            {health.cpu.cores_physical} nucleos · {health.cpu.freq_mhz} MHz
          </p>
        </div>

        {/* Memory */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col items-center">
          <CircularGauge percent={health.memory.percent} color={memColor} icon={MemoryStick} />
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-3">Memoria RAM</h3>
          <p className="text-[11px] text-gray-400">
            {health.memory.used_gb} / {health.memory.total_gb} GB
          </p>
        </div>

        {/* GPU */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col items-center">
          <CircularGauge
            percent={gpuAvailable ? gpu.utilization_percent : 0}
            color={gpuColor}
            icon={Zap}
          />
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-3">GPU</h3>
          <p className="text-[11px] text-gray-400">
            {gpuAvailable ? gpu.name : "No disponible"}
          </p>
        </div>

        {/* Disk */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col items-center">
          <CircularGauge percent={health.disk.percent} color={diskColor} icon={HardDrive} />
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-3">Disco Principal</h3>
          <p className="text-[11px] text-gray-400">
            {health.disk.used_gb} / {health.disk.total_gb} GB
          </p>
        </div>
      </div>

      {/* ── CPU per Core + GPU Details ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* CPU per Core */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-4 h-4 text-blue-500" />
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">CPU por Nucleo</h3>
          </div>
          <div className="space-y-3">
            {(health.cpu.per_core || []).map((pct: number, i: number) => (
              <div key={i} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 dark:text-gray-400 w-14">Core {i}</span>
                <div className="flex-1">
                  <ProgressBar percent={pct} color={pct > 80 ? "red" : pct > 60 ? "orange" : "blue"} />
                </div>
                <span className="text-xs font-medium text-gray-600 dark:text-gray-300 w-10 text-right">
                  {Math.round(pct)}%
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700 flex justify-between text-[11px] text-gray-400">
            <span>
              Load Average: {health.cpu.load_avg?.join(" / ") || "N/A"}
            </span>
            <span>
              {health.cpu.cores_physical} fisicos · {health.cpu.cores_logical} logicos
            </span>
          </div>
        </div>

        {/* GPU Details */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-purple-500" />
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">GPU NVIDIA</h3>
            </div>
            {gpuAvailable && (
              <span className="text-[10px] bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-1 rounded">
                {gpu.name}
              </span>
            )}
          </div>

          {gpuAvailable ? (
            <>
              {/* Utilization */}
              <div className="space-y-3 mb-6">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                    <Activity className="w-3 h-3" /> Utilizacion
                  </span>
                  <span className={`text-sm font-bold ${gpu.utilization_percent > 80 ? "text-orange-500" : "text-emerald-500"}`}>
                    {gpu.utilization_percent}%
                  </span>
                </div>
                <ProgressBar percent={gpu.utilization_percent} color={gpu.utilization_percent > 80 ? "orange" : "purple"} />

                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                    <Monitor className="w-3 h-3" /> VRAM
                  </span>
                  <span className="text-xs text-gray-600 dark:text-gray-300">
                    {gpu.memory_used_mb} / {gpu.memory_total_mb} MB
                  </span>
                </div>
                <ProgressBar percent={vramPercent} color={vramPercent > 85 ? "red" : "orange"} />
              </div>

              {/* GPU Stats Row */}
              <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <div className="text-center">
                  <Thermometer className={`w-5 h-5 mx-auto mb-1 ${gpu.temperature_c > 80 ? "text-red-500" : "text-orange-400"}`} />
                  <p className={`text-lg font-bold ${gpu.temperature_c > 80 ? "text-red-500" : "text-orange-400"}`}>
                    {gpu.temperature_c}°C
                  </p>
                  <p className="text-[10px] text-gray-400">Temperatura</p>
                </div>
                <div className="text-center">
                  <Fan className="w-5 h-5 mx-auto mb-1 text-blue-400 animate-spin" style={{ animationDuration: "3s" }} />
                  <p className="text-lg font-bold text-blue-400">
                    {gpu.fan_percent}%
                  </p>
                  <p className="text-[10px] text-gray-400">Ventilador</p>
                </div>
                <div className="text-center">
                  <Zap className="w-5 h-5 mx-auto mb-1 text-yellow-400" />
                  <p className="text-lg font-bold text-yellow-400">
                    {gpu.power_draw_w}W
                  </p>
                  <p className="text-[10px] text-gray-400">/ {gpu.power_limit_w}W</p>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
              GPU no disponible
            </div>
          )}
        </div>
      </div>

      {/* ── Memory + Storage ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Memory */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <MemoryStick className="w-4 h-4 text-emerald-500" />
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Memoria</h3>
          </div>

          {/* RAM */}
          <div className="space-y-2 mb-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400">RAM</span>
              <span className="text-xs text-gray-600 dark:text-gray-300 font-medium">
                {health.memory.used_gb} / {health.memory.total_gb} GB
              </span>
            </div>
            <ProgressBar percent={health.memory.percent} color="green" />
            <div className="flex justify-between text-[11px] text-gray-400">
              <span>Usada: {health.memory.used_gb} GB</span>
              <span>Disponible: {health.memory.available_gb} GB</span>
            </div>
          </div>

          {/* Swap */}
          <div className="space-y-2 pt-3 border-t border-gray-100 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400">Swap</span>
              <span className="text-xs text-gray-600 dark:text-gray-300 font-medium">
                {health.swap?.used_gb || 0} / {health.swap?.total_gb || 0} GB
              </span>
            </div>
            <ProgressBar
              percent={health.swap?.percent || 0}
              color={health.swap?.percent > 50 ? "red" : "orange"}
            />
          </div>
        </div>

        {/* Storage */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <HardDrive className="w-4 h-4 text-blue-500" />
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Almacenamiento</h3>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                {health.disk.device || "/dev/sda"}
              </span>
              <span className="text-xs text-gray-600 dark:text-gray-300 font-medium">
                {health.disk.used_gb} / {health.disk.total_gb} GB
              </span>
            </div>
            <ProgressBar percent={health.disk.percent} color="blue" />
            <div className="flex justify-between text-[11px] text-gray-400">
              <span>{health.disk.mount || "/"}</span>
              <span>Libre: {health.disk.free_gb} GB</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer: System Specs ── */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl px-6 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[11px] text-gray-400">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3 h-3" />
            Uptime: <strong className="text-gray-600 dark:text-gray-300">{health.uptime?.formatted}</strong>
          </span>
          <span className="flex items-center gap-1.5">
            <Cpu className="w-3 h-3" />
            {health.cpu.cores_physical} cores · {health.cpu.freq_mhz} MHz
          </span>
          <span className="flex items-center gap-1.5">
            <MemoryStick className="w-3 h-3" />
            {health.memory.total_gb} GB RAM
          </span>
          <span className="flex items-center gap-1.5">
            <Zap className="w-3 h-3" />
            {gpuAvailable ? `${gpu.name} · ${gpu.memory_total_mb} MB VRAM` : "Sin GPU"}
          </span>
          <span className="flex items-center gap-1.5">
            <HardDrive className="w-3 h-3" />
            {health.disk.total_gb} GB total
          </span>
        </div>
      </div>

      {/* ── Alert History ── */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Historial de Alertas
            </h3>
            {alerts.length > 0 && (
              <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {alerts.length}
              </span>
            )}
          </div>
          {alerts.length > 0 && (
            <button
              onClick={() => setAlerts([])}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <Trash2 className="w-3 h-3" /> Limpiar
            </button>
          )}
        </div>

        {alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-3 py-2 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 rounded-lg text-xs"
              >
                <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                {alert}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400 text-center py-4">
            Sin alertas activas — todos los recursos dentro de limites normales
          </p>
        )}
      </div>
    </div>
  );
}

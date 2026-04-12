"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  Camera,
  Settings,
  Bell,
  Image,
  Wifi,
  WifiOff,
  RefreshCw,
  Maximize2,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CameraDetailPage() {
  const params = useParams();
  const router = useRouter();
  const cameraId = params.id as string;

  const [camera, setCamera] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<
    "live" | "config" | "detections" | "image" | "events"
  >("live");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [cam, evts] = await Promise.all([
          api.getCamera(cameraId),
          api.getEvents({ camera_id: cameraId, limit: "20" }),
        ]);
        setCamera(cam);
        setEvents(evts);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [cameraId]);

  if (loading || !camera) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-text-muted">Cargando camara...</div>
      </div>
    );
  }

  const tabs = [
    { key: "live", label: "En Vivo", icon: Camera },
    { key: "config", label: "Configuracion", icon: Settings },
    { key: "detections", label: "Detecciones", icon: Bell },
    { key: "image", label: "Imagen", icon: Image },
    { key: "events", label: "Eventos", icon: Bell },
  ] as const;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-surface-hover transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-text-secondary" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-text-primary">
              {camera.name}
            </h1>
            <span
              className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
                camera.status === "online"
                  ? "bg-success/20 text-success"
                  : "bg-danger/20 text-danger"
              }`}
            >
              {camera.status === "online" ? (
                <Wifi className="w-3 h-3" />
              ) : (
                <WifiOff className="w-3 h-3" />
              )}
              {camera.status}
            </span>
          </div>
          <p className="text-text-muted text-sm">
            {camera.location || "Sin ubicacion"} | {camera.brand}{" "}
            {camera.model || ""}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-primary text-primary"
                  : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === "live" && (
        <LiveView cameraId={cameraId} cameraName={camera.name} status={camera.status} />
      )}

      {activeTab === "config" && (
        <div className="bg-surface border border-border rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-text-primary">
            Configuracion de la Camara
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <InfoField label="RTSP Principal" value={camera.rtsp_url} />
            <InfoField
              label="RTSP Sub-stream"
              value={camera.rtsp_sub_url || "No configurado"}
            />
            <InfoField label="Grabacion" value={camera.recording_enabled ? "Activa" : "Desactivada"} />
            <InfoField label="Habilitada" value={camera.enabled ? "Si" : "No"} />
          </div>
          <h3 className="text-sm font-semibold text-text-primary pt-4">
            Motion Gate
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <InfoField
              label="Threshold ON"
              value={`${(camera.config?.motion_on_threshold || 0.005) * 100}%`}
            />
            <InfoField
              label="Off Frames"
              value={camera.config?.motion_off_frames || 30}
            />
            <InfoField
              label="FPS Deteccion"
              value={camera.config?.detection_fps || 10}
            />
            <InfoField
              label="Resolucion"
              value={camera.config?.resolution || "1280x720"}
            />
          </div>
        </div>
      )}

      {activeTab === "detections" && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Detecciones Recientes
          </h2>
          <div className="space-y-2">
            {events.length === 0 ? (
              <p className="text-text-muted text-sm text-center py-8">
                Sin detecciones
              </p>
            ) : (
              events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between p-3 bg-background rounded-lg"
                >
                  <div>
                    <p className="text-sm text-text-primary font-medium capitalize">
                      {event.label}
                    </p>
                    <p className="text-xs text-text-muted">
                      {event.event_type} | Conf:{" "}
                      {Math.round(event.confidence * 100)}%
                    </p>
                  </div>
                  <p className="text-xs text-text-muted">
                    {formatDate(event.detected_at)}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === "image" && (
        <div className="bg-surface border border-border rounded-xl p-6">
          <p className="text-text-muted text-sm text-center py-8">
            Configuracion de imagen (brillo, contraste, rotacion) — disponible
            proximamente
          </p>
        </div>
      )}

      {activeTab === "events" && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Historial de Eventos
          </h2>
          <div className="space-y-2">
            {events.map((event) => (
              <div
                key={event.id}
                className="flex items-center gap-4 p-3 bg-background rounded-lg"
              >
                {event.snapshot_url && (
                  <div className="w-16 h-12 bg-surface-hover rounded flex items-center justify-center shrink-0">
                    <Image className="w-4 h-4 text-text-muted" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text-primary capitalize">
                    {event.label}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatDate(event.detected_at)}
                  </p>
                </div>
                <span className="text-xs text-text-secondary">
                  {event.review_pass}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LiveView({ cameraId, cameraName, status }: { cameraId: string; cameraName: string; status: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(2); // seconds
  const [isFullscreen, setIsFullscreen] = useState(false);

  const fetchSnapshot = () => {
    const token = localStorage.getItem("access_token");
    if (!token || status !== "online") return;

    fetch(`${API_URL}/api/cameras/${cameraId}/snapshot`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed");
        return res.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
        setError(false);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchSnapshot();
    const iv = setInterval(fetchSnapshot, refreshInterval * 1000);
    return () => clearInterval(iv);
  }, [cameraId, refreshInterval, status]);

  if (status !== "online") {
    return (
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="aspect-video bg-background flex items-center justify-center">
          <div className="text-center">
            <WifiOff className="w-16 h-16 text-danger mx-auto mb-3" />
            <p className="text-text-secondary">Camara offline</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className={`bg-surface border border-border rounded-xl overflow-hidden ${isFullscreen ? "fixed inset-0 z-50 rounded-none" : ""}`}>
        <div className={`relative ${isFullscreen ? "h-full" : "aspect-video"} bg-background flex items-center justify-center`}>
          {loading && !src && (
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-primary mx-auto mb-2 animate-spin" />
              <p className="text-text-muted text-sm">Conectando...</p>
            </div>
          )}
          {src && (
            <img
              src={src}
              alt={cameraName}
              className={`${isFullscreen ? "h-full" : "w-full h-full"} object-contain`}
            />
          )}
          {error && !src && (
            <div className="text-center">
              <Camera className="w-16 h-16 text-text-muted mx-auto mb-3" />
              <p className="text-text-secondary">Error al conectar</p>
              <button onClick={fetchSnapshot} className="mt-2 text-xs text-primary hover:underline">
                Reintentar
              </button>
            </div>
          )}
          {/* Live badge */}
          {src && (
            <div className="absolute top-3 left-3 flex items-center gap-2">
              <span className="flex items-center gap-1.5 bg-danger/90 text-white text-xs px-2.5 py-1 rounded-full">
                <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                EN VIVO
              </span>
            </div>
          )}
          {/* Fullscreen toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="absolute top-3 right-3 p-2 bg-black/50 hover:bg-black/70 rounded-lg transition-colors"
          >
            <Maximize2 className="w-4 h-4 text-white" />
          </button>
          {/* Camera info overlay */}
          {src && (
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4">
              <p className="text-white text-sm font-medium">{cameraName}</p>
              <p className="text-white/70 text-xs">{new Date().toLocaleString()}</p>
            </div>
          )}
        </div>
      </div>
      {/* Refresh interval selector */}
      <div className="flex items-center gap-3 text-xs text-text-muted">
        <span>Actualizar cada:</span>
        {[1, 2, 5, 10].map((s) => (
          <button
            key={s}
            onClick={() => setRefreshInterval(s)}
            className={`px-2 py-1 rounded ${
              refreshInterval === s
                ? "bg-primary text-white"
                : "bg-surface border border-border text-text-secondary hover:text-text-primary"
            }`}
          >
            {s}s
          </button>
        ))}
      </div>
    </div>
  );
}

function InfoField({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className="text-sm text-text-primary font-mono break-all">
        {String(value)}
      </p>
    </div>
  );
}

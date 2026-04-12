"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Camera, Plus, Wifi, WifiOff, Settings, Trash2, RefreshCw } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [gridSize, setGridSize] = useState<"2x2" | "3x3" | "4x4">("3x3");

  const [snapTs, setSnapTs] = useState(Date.now());

  useEffect(() => {
    loadCameras();
    // Refresh snapshots every 10 seconds
    const iv = setInterval(() => setSnapTs(Date.now()), 10000);
    return () => clearInterval(iv);
  }, []);

  async function loadCameras() {
    try {
      const data = await api.getCameras();
      setCameras(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const gridCols = {
    "2x2": "grid-cols-1 md:grid-cols-2",
    "3x3": "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
    "4x4": "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Camaras</h1>
          <p className="text-text-muted text-sm mt-1">
            {cameras.length} camaras configuradas
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Grid Size Selector */}
          <div className="flex bg-surface border border-border rounded-lg overflow-hidden">
            {(["2x2", "3x3", "4x4"] as const).map((size) => (
              <button
                key={size}
                onClick={() => setGridSize(size)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  gridSize === size
                    ? "bg-primary text-white"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {size}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Agregar
          </button>
        </div>
      </div>

      {/* Camera Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-text-muted">
            Cargando camaras...
          </div>
        </div>
      ) : cameras.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-surface border border-border rounded-xl">
          <Camera className="w-12 h-12 text-text-muted mb-3" />
          <p className="text-text-secondary">Sin camaras configuradas</p>
          <button
            onClick={() => setShowAdd(true)}
            className="mt-4 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm rounded-lg transition-colors"
          >
            Agregar primera camara
          </button>
        </div>
      ) : (
        <div className={`grid ${gridCols[gridSize]} gap-4`}>
          {cameras.map((cam) => (
            <Link
              key={cam.id}
              href={`/dashboard/cameras/${cam.id}`}
              className="group bg-surface border border-border rounded-xl overflow-hidden hover:border-border-hover transition-all"
            >
              {/* Video Preview Area */}
              <div className="relative aspect-video bg-background flex items-center justify-center overflow-hidden">
                {cam.status === "online" ? (
                  <CameraSnapshot camId={cam.id} camName={cam.name} ts={snapTs} />
                ) : null}
                <Camera className={`w-8 h-8 text-text-muted ${cam.status === "online" ? "hidden" : ""}`} />
                {/* Status Badge */}
                <div className="absolute top-2 left-2">
                  <span
                    className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
                      cam.status === "online"
                        ? "bg-success/20 text-success"
                        : "bg-danger/20 text-danger"
                    }`}
                  >
                    {cam.status === "online" ? (
                      <Wifi className="w-3 h-3" />
                    ) : (
                      <WifiOff className="w-3 h-3" />
                    )}
                    {cam.status}
                  </span>
                </div>
                {/* Recording indicator */}
                {cam.recording_enabled && cam.status === "online" && (
                  <div className="absolute top-2 right-2 flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-danger animate-pulse" />
                    <span className="text-[10px] text-danger font-medium">
                      REC
                    </span>
                  </div>
                )}
              </div>

              {/* Camera Info */}
              <div className="p-3">
                <h3 className="text-sm font-semibold text-text-primary group-hover:text-primary transition-colors">
                  {cam.name}
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  {cam.location || "Sin ubicacion"}
                </p>
                {cam.brand && (
                  <p className="text-xs text-text-muted mt-1">
                    {cam.brand} {cam.model || ""}
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Add Camera Modal */}
      {showAdd && (
        <AddCameraModal
          onClose={() => setShowAdd(false)}
          onAdded={() => {
            setShowAdd(false);
            loadCameras();
          }}
        />
      )}
    </div>
  );
}

function AddCameraModal({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: () => void;
}) {
  const [form, setForm] = useState({
    name: "",
    rtsp_url: "",
    rtsp_sub_url: "",
    location: "",
    brand: "",
    model: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.createCamera(form);
      onAdded();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-lg">
        <h2 className="text-lg font-bold text-text-primary mb-4">
          Agregar Camara
        </h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            placeholder="Nombre de la camara"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            required
          />
          <input
            type="text"
            placeholder="URL RTSP principal (rtsp://...)"
            value={form.rtsp_url}
            onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            required
          />
          <input
            type="text"
            placeholder="URL RTSP sub-stream (opcional)"
            value={form.rtsp_sub_url}
            onChange={(e) => setForm({ ...form, rtsp_sub_url: e.target.value })}
            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Ubicacion"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            />
            <input
              type="text"
              placeholder="Marca"
              value={form.brand}
              onChange={(e) => setForm({ ...form, brand: e.target.value })}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            />
          </div>
          {error && (
            <p className="text-danger text-sm">{error}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CameraSnapshot({ camId, camName, ts }: { camId: string; camName: string; ts: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem("access_token");
    if (!token) return;

    fetch(`${API_URL}/api/cameras/${camId}/snapshot`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed");
        return res.blob();
      })
      .then((blob) => {
        if (!cancelled) {
          setSrc(URL.createObjectURL(blob));
          setError(false);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [camId, ts]);

  if (error || !src) {
    return <Camera className="w-8 h-8 text-text-muted" />;
  }

  return (
    <img
      src={src}
      alt={camName}
      className="w-full h-full object-cover"
    />
  );
}

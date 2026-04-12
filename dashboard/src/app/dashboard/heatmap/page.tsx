"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Flame, Camera } from "lucide-react";

export default function HeatmapPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [selectedCamera, setSelectedCamera] = useState("");
  const [timeRange, setTimeRange] = useState("24h");

  useEffect(() => {
    async function load() {
      try {
        const cams = await api.getCameras();
        setCameras(cams);
        if (cams.length > 0) setSelectedCamera(cams[0].id);
      } catch (err) {
        console.error(err);
      }
    }
    load();
  }, []);

  // Generate sample heatmap grid for visualization
  const gridSize = 20;
  const heatmapGrid = Array.from({ length: gridSize }, () =>
    Array.from({ length: gridSize }, () => Math.random())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Mapa de Calor</h1>
        <p className="text-text-muted text-sm mt-1">
          Visualizacion de densidad de actividad por camara
        </p>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <select
          value={selectedCamera}
          onChange={(e) => setSelectedCamera(e.target.value)}
          className="px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
        >
          {cameras.map((cam) => (
            <option key={cam.id} value={cam.id}>
              {cam.name}
            </option>
          ))}
        </select>
        <div className="flex bg-surface border border-border rounded-lg overflow-hidden">
          {["1h", "6h", "24h", "7d"].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                timeRange === range
                  ? "bg-primary text-white"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap Visualization */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="aspect-video bg-background rounded-lg relative overflow-hidden">
          {/* Camera frame placeholder */}
          <div className="absolute inset-0 flex items-center justify-center">
            <Camera className="w-16 h-16 text-text-muted/20" />
          </div>

          {/* Heatmap overlay */}
          <div
            className="absolute inset-0 grid"
            style={{
              gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
              gridTemplateRows: `repeat(${gridSize}, 1fr)`,
            }}
          >
            {heatmapGrid.flat().map((value, i) => (
              <div
                key={i}
                className="transition-colors"
                style={{
                  backgroundColor:
                    value > 0.7
                      ? `rgba(239, 68, 68, ${value * 0.6})`
                      : value > 0.4
                      ? `rgba(245, 158, 11, ${value * 0.5})`
                      : value > 0.15
                      ? `rgba(59, 130, 246, ${value * 0.4})`
                      : "transparent",
                }}
              />
            ))}
          </div>
        </div>

        {/* Color Legend */}
        <div className="flex items-center justify-center gap-6 mt-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 rounded bg-blue-500/40" />
            <span className="text-xs text-text-muted">Baja</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 rounded bg-warning/50" />
            <span className="text-xs text-text-muted">Media</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-3 rounded bg-danger/60" />
            <span className="text-xs text-text-muted">Alta</span>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { ArrowRightLeft, TrendingUp, Users, ArrowUpRight, ArrowDownRight } from "lucide-react";

export default function TrafficPage() {
  const [timeRange, setTimeRange] = useState("24h");

  // Sample data
  const zones = [
    { name: "Entrada Principal", in: 234, out: 198, occupancy: 36 },
    { name: "Estacionamiento", in: 89, out: 72, occupancy: 17 },
    { name: "Zona Carga", in: 12, out: 10, occupancy: 2 },
    { name: "Acceso Peatonal", in: 156, out: 143, occupancy: 13 },
  ];

  const totalIn = zones.reduce((s, z) => s + z.in, 0);
  const totalOut = zones.reduce((s, z) => s + z.out, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Trafico</h1>
        <p className="text-text-muted text-sm mt-1">
          Ocupacion y flujos de trafico por zona
        </p>
      </div>

      {/* Time Range */}
      <div className="flex bg-surface border border-border rounded-lg overflow-hidden w-fit">
        {["1h", "6h", "24h", "7d"].map((range) => (
          <button
            key={range}
            onClick={() => setTimeRange(range)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              timeRange === range
                ? "bg-primary text-white"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {range}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
              <ArrowUpRight className="w-5 h-5 text-success" />
            </div>
            <span className="text-sm text-text-secondary">Entradas</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{totalIn}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
              <ArrowDownRight className="w-5 h-5 text-warning" />
            </div>
            <span className="text-sm text-text-secondary">Salidas</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{totalOut}</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-accent" />
            </div>
            <span className="text-sm text-text-secondary">Ocupacion Actual</span>
          </div>
          <p className="text-2xl font-bold text-text-primary">{totalIn - totalOut}</p>
        </div>
      </div>

      {/* Zones Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-xs text-text-muted font-medium px-5 py-3">Zona</th>
              <th className="text-right text-xs text-text-muted font-medium px-5 py-3">Entradas</th>
              <th className="text-right text-xs text-text-muted font-medium px-5 py-3">Salidas</th>
              <th className="text-right text-xs text-text-muted font-medium px-5 py-3">Ocupacion</th>
              <th className="text-right text-xs text-text-muted font-medium px-5 py-3">Flujo</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((zone, i) => (
              <tr key={i} className="border-b border-border/50 hover:bg-surface-hover transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <ArrowRightLeft className="w-4 h-4 text-accent" />
                    <span className="text-sm text-text-primary">{zone.name}</span>
                  </div>
                </td>
                <td className="text-right px-5 py-3">
                  <span className="text-sm text-success">{zone.in}</span>
                </td>
                <td className="text-right px-5 py-3">
                  <span className="text-sm text-warning">{zone.out}</span>
                </td>
                <td className="text-right px-5 py-3">
                  <span className="text-sm text-text-primary font-medium">{zone.occupancy}</span>
                </td>
                <td className="text-right px-5 py-3">
                  <div className="w-20 h-1.5 bg-background rounded-full overflow-hidden ml-auto">
                    <div
                      className="h-full bg-accent rounded-full"
                      style={{ width: `${(zone.in / totalIn) * 100}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

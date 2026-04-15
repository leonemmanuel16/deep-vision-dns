"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Bell,
  Filter,
  Search,
  Image,
  ChevronRight,
  User,
  UserX,
  UserCheck,
} from "lucide-react";

function SnapshotThumbnail({ snapshotUrl }: { snapshotUrl: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let revoke: string | null = null;
    api
      .fetchSnapshot(snapshotUrl)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        revoke = url;
        setSrc(url);
      })
      .catch(() => {});
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [snapshotUrl]);

  if (!src) {
    return (
      <div className="w-12 h-9 bg-background rounded flex items-center justify-center">
        <Image className="w-4 h-4 text-text-muted" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt="snapshot"
      className="w-12 h-9 rounded object-cover"
    />
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/* Person badge for events                                         */
/* ═══════════════════════════════════════════════════════════════ */

function PersonBadge({ event }: { event: any }) {
  const attrs = event.attributes || {};
  const faceName = attrs.face_match;
  const isUnknown = !faceName && attrs.face_detected;
  const hasPerson = event.person_id;

  // Known person matched
  if (faceName && !faceName.startsWith("Desconocido")) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-500/10 text-green-400 font-medium">
        <UserCheck className="w-3 h-3" />
        {faceName}
      </span>
    );
  }

  // Unknown person (Desconocido #N)
  if (faceName && faceName.startsWith("Desconocido")) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-orange-500/10 text-orange-400 font-medium">
        <UserX className="w-3 h-3" />
        {faceName}
      </span>
    );
  }

  // Face detected but no match info in attributes — check person_id
  if (hasPerson) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-500/10 text-blue-400">
        <User className="w-3 h-3" />
        Identificado
      </span>
    );
  }

  // Person detection but no face analysis
  if (event.label === "person") {
    return (
      <span className="text-xs text-text-muted">
        Sin rostro
      </span>
    );
  }

  // Not a person
  return <span className="text-xs text-text-muted">—</span>;
}

/* ═══════════════════════════════════════════════════════════════ */
/* Label names in Spanish                                          */
/* ═══════════════════════════════════════════════════════════════ */

const LABEL_NAMES: Record<string, string> = {
  person: "Persona",
  car: "Auto",
  truck: "Camion",
  bus: "Autobus",
  motorcycle: "Moto",
  bicycle: "Bicicleta",
  cat: "Gato",
  dog: "Perro",
};

const EVENT_TYPE_NAMES: Record<string, string> = {
  person_detected: "Persona detectada",
  vehicle_detected: "Vehiculo detectado",
  bicycle_detected: "Bicicleta detectada",
  animal_detected: "Animal detectado",
  object_detected: "Objeto detectado",
};

export default function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    label: "",
    event_type: "",
  });

  useEffect(() => {
    loadEvents();
  }, []);

  async function loadEvents() {
    try {
      const params: Record<string, string> = { limit: "100" };
      if (filters.label) params.label = filters.label;
      if (filters.event_type) params.event_type = filters.event_type;
      const data = await api.getEvents(params);
      setEvents(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const labelColors: Record<string, string> = {
    person: "bg-success/10 text-success",
    car: "bg-warning/10 text-warning",
    truck: "bg-orange-500/10 text-orange-400",
    bus: "bg-blue-500/10 text-blue-400",
    motorcycle: "bg-purple-500/10 text-purple-400",
    bicycle: "bg-cyan-500/10 text-cyan-400",
    dog: "bg-amber-500/10 text-amber-400",
    cat: "bg-pink-500/10 text-pink-400",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Eventos</h1>
          <p className="text-text-muted text-sm mt-1">
            Historial global de detecciones
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Filtrar por tipo..."
            className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
          />
        </div>
        <select
          value={filters.label}
          onChange={(e) => setFilters({ ...filters, label: e.target.value })}
          className="px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary"
        >
          <option value="">Todos los objetos</option>
          <option value="person">Persona</option>
          <option value="car">Auto</option>
          <option value="truck">Camion</option>
          <option value="bus">Autobus</option>
          <option value="motorcycle">Moto</option>
        </select>
        <button
          onClick={loadEvents}
          className="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Events List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-text-muted">
            Cargando eventos...
          </div>
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-surface border border-border rounded-xl">
          <Bell className="w-12 h-12 text-text-muted mb-3" />
          <p className="text-text-secondary">Sin eventos registrados</p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Snapshot
                </th>
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Tipo
                </th>
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Evento
                </th>
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Persona
                </th>
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Confianza
                </th>
                <th className="text-left text-xs text-text-muted font-medium px-4 py-3">
                  Fecha
                </th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr
                  key={event.id}
                  className="border-b border-border/50 hover:bg-surface-hover transition-colors"
                >
                  <td className="px-4 py-3">
                    {event.snapshot_url ? (
                      <SnapshotThumbnail snapshotUrl={event.snapshot_url} />
                    ) : (
                      <div className="w-12 h-9 bg-background rounded flex items-center justify-center">
                        <Image className="w-4 h-4 text-text-muted" />
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full capitalize ${
                        labelColors[event.label] || "bg-muted/10 text-muted"
                      }`}
                    >
                      {LABEL_NAMES[event.label] || event.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-text-secondary">
                    {EVENT_TYPE_NAMES[event.event_type] || event.event_type}
                  </td>
                  <td className="px-4 py-3">
                    <PersonBadge event={event} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-background rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{
                            width: `${event.confidence * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs text-text-muted">
                        {Math.round(event.confidence * 100)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-text-muted">
                    {formatDate(event.detected_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/dashboard/events/${event.id}`}
                      className="text-text-muted hover:text-primary transition-colors"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

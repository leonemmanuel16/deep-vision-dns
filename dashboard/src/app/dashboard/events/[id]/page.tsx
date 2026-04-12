"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Image, Video, User, Car } from "lucide-react";

function AuthenticatedSnapshot({
  snapshotUrl,
  alt,
  className,
}: {
  snapshotUrl: string;
  alt: string;
  className?: string;
}) {
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
    return <Image className="w-12 h-12 text-text-muted" />;
  }

  return <img src={src} alt={alt} className={className} />;
}

export default function EventDetailPage() {
  const params = useParams();
  const router = useRouter();
  const eventId = params.id as string;
  const [event, setEvent] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getEvent(eventId);
        setEvent(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [eventId]);

  if (loading || !event) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-text-muted">Cargando evento...</div>
      </div>
    );
  }

  const attrs = event.attributes || {};
  const hasPersonAttrs = event.label === "person" && Object.values(attrs).some(Boolean);
  const hasVehicleAttrs = ["car", "truck", "bus"].includes(event.label) && Object.values(attrs).some(Boolean);

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-surface-hover transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-text-secondary" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-text-primary capitalize">
            {event.label} - {event.event_type}
          </h1>
          <p className="text-text-muted text-sm">
            {formatDate(event.detected_at)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Snapshot */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="aspect-video bg-background flex items-center justify-center">
            {event.snapshot_url ? (
              <AuthenticatedSnapshot
                snapshotUrl={event.snapshot_url}
                alt="Snapshot"
                className="w-full h-full object-contain"
              />
            ) : (
              <Image className="w-12 h-12 text-text-muted" />
            )}
          </div>
          {event.clip_url && (
            <div className="p-3 border-t border-border">
              <button className="flex items-center gap-2 text-sm text-primary hover:text-primary-hover">
                <Video className="w-4 h-4" />
                Ver clip de video
              </button>
            </div>
          )}
        </div>

        {/* Details */}
        <div className="space-y-4">
          {/* Basic Info */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-text-primary">
              Detalles
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <Detail label="Tipo" value={event.event_type} />
              <Detail label="Objeto" value={event.label} />
              <Detail
                label="Confianza"
                value={`${Math.round(event.confidence * 100)}%`}
              />
              <Detail label="Tracker ID" value={event.tracker_id || "N/A"} />
              <Detail label="Review" value={event.review_pass} />
              <Detail
                label="Deep Review"
                value={event.needs_deep_review ? "Pendiente" : "Completado"}
              />
            </div>
          </div>

          {/* Person Attributes */}
          {hasPersonAttrs && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <User className="w-4 h-4 text-success" />
                Atributos de Persona
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {attrs.ropa_sup_color && (
                  <Detail label="Ropa Superior" value={`${attrs.ropa_sup_tipo} ${attrs.ropa_sup_color}`} />
                )}
                {attrs.ropa_inf_color && (
                  <Detail label="Ropa Inferior" value={`${attrs.ropa_inf_tipo} ${attrs.ropa_inf_color}`} />
                )}
                {attrs.casco !== null && (
                  <Detail label="Casco" value={attrs.casco ? "Si" : "No"} />
                )}
                {attrs.chaleco !== null && (
                  <Detail label="Chaleco" value={attrs.chaleco ? "Si" : "No"} />
                )}
                {attrs.genero_estimado && (
                  <Detail label="Genero Est." value={attrs.genero_estimado} />
                )}
                {attrs.edad_estimada && (
                  <Detail label="Edad Est." value={attrs.edad_estimada} />
                )}
              </div>
            </div>
          )}

          {/* Vehicle Attributes */}
          {hasVehicleAttrs && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Car className="w-4 h-4 text-warning" />
                Atributos de Vehiculo
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {attrs.tipo_vehiculo && (
                  <Detail label="Tipo" value={attrs.tipo_vehiculo} />
                )}
                {attrs.color_vehiculo && (
                  <Detail label="Color" value={attrs.color_vehiculo} />
                )}
                {attrs.placa_texto && (
                  <Detail label="Placa" value={attrs.placa_texto} />
                )}
                {attrs.marca_estimada && (
                  <Detail label="Marca" value={attrs.marca_estimada} />
                )}
              </div>
            </div>
          )}

          {/* BBox */}
          {event.bbox && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
              <h2 className="text-sm font-semibold text-text-primary">
                Bounding Box
              </h2>
              <pre className="text-xs text-text-secondary font-mono bg-background p-3 rounded-lg">
                {JSON.stringify(event.bbox, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-sm text-text-primary capitalize">{String(value)}</p>
    </div>
  );
}

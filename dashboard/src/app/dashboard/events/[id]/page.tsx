"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  Image,
  Video,
  User,
  Car,
  AlertTriangle,
  Shield,
  Eye,
  MapPin,
  Clock,
  Target,
  Maximize2,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════ */
/* Event type labels & styling                                    */
/* ═══════════════════════════════════════════════════════════════ */

const EVENT_TYPE_INFO: Record<
  string,
  { label: string; reason: string; color: string; icon: string }
> = {
  person_detected: {
    label: "Persona Detectada",
    reason: "Se detecto una persona en el area de monitoreo",
    color: "#22c55e",
    icon: "👤",
  },
  vehicle_detected: {
    label: "Vehiculo Detectado",
    reason: "Se detecto un vehiculo en movimiento en la zona",
    color: "#3b82f6",
    icon: "🚗",
  },
  bicycle_detected: {
    label: "Bicicleta Detectada",
    reason: "Se detecto una bicicleta en el area",
    color: "#8b5cf6",
    icon: "🚲",
  },
  animal_detected: {
    label: "Animal Detectado",
    reason: "Se detecto un animal en la zona de monitoreo",
    color: "#f59e0b",
    icon: "🐾",
  },
  face_recognized: {
    label: "Rostro Reconocido",
    reason: "Se identifico un rostro registrado en la base de datos",
    color: "#06b6d4",
    icon: "🧑",
  },
  unknown_face: {
    label: "Rostro Desconocido",
    reason: "Se detecto un rostro que no esta registrado en el sistema",
    color: "#ef4444",
    icon: "❓",
  },
  object_detected: {
    label: "Objeto Detectado",
    reason: "Se detecto un objeto relevante en la zona",
    color: "#6b7280",
    icon: "📦",
  },
};

const LABEL_NAMES: Record<string, string> = {
  person: "Persona",
  car: "Auto",
  truck: "Camion",
  bus: "Autobus",
  motorcycle: "Motocicleta",
  bicycle: "Bicicleta",
  cat: "Gato",
  dog: "Perro",
};

/* ═══════════════════════════════════════════════════════════════ */
/* Snapshot with bbox overlay                                     */
/* ═══════════════════════════════════════════════════════════════ */

function SnapshotWithOverlay({
  snapshotUrl,
  bbox,
  label,
  confidence,
  eventType,
  trackerId,
  personName,
}: {
  snapshotUrl: string;
  bbox?: { x1: number; y1: number; x2: number; y2: number };
  label: string;
  confidence: number;
  eventType: string;
  trackerId?: number;
  personName?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  const eventInfo = EVENT_TYPE_INFO[eventType] || EVENT_TYPE_INFO.object_detected;
  const bboxColor = eventInfo.color;

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

  const updateSizes = useCallback(() => {
    if (imgRef.current && containerRef.current) {
      const img = imgRef.current;
      const cont = containerRef.current;
      setImgSize({ w: img.naturalWidth, h: img.naturalHeight });
      setContainerSize({ w: cont.clientWidth, h: cont.clientHeight });
    }
  }, []);

  useEffect(() => {
    window.addEventListener("resize", updateSizes);
    return () => window.removeEventListener("resize", updateSizes);
  }, [updateSizes]);

  if (!src) {
    return (
      <div className="aspect-video bg-background flex items-center justify-center">
        <Image className="w-12 h-12 text-text-muted" />
      </div>
    );
  }

  // Calculate bbox position relative to displayed image
  let overlayStyle: React.CSSProperties | null = null;
  let labelStyle: React.CSSProperties | null = null;

  if (bbox && imgSize.w > 0 && containerSize.w > 0) {
    // Image is displayed with object-contain, so we need to calculate
    // the actual rendered image dimensions within the container
    const imgAspect = imgSize.w / imgSize.h;
    const contAspect = containerSize.w / containerSize.h;

    let renderedW: number, renderedH: number, offsetX: number, offsetY: number;

    if (imgAspect > contAspect) {
      // Image is wider — fits width, letterbox top/bottom
      renderedW = containerSize.w;
      renderedH = containerSize.w / imgAspect;
      offsetX = 0;
      offsetY = (containerSize.h - renderedH) / 2;
    } else {
      // Image is taller — fits height, pillarbox left/right
      renderedH = containerSize.h;
      renderedW = containerSize.h * imgAspect;
      offsetX = (containerSize.w - renderedW) / 2;
      offsetY = 0;
    }

    // Determine if bbox is in pixels or normalized (0-1)
    let x1 = bbox.x1,
      y1 = bbox.y1,
      x2 = bbox.x2,
      y2 = bbox.y2;

    // If all values are <= 1, they're normalized
    if (x1 <= 1 && y1 <= 1 && x2 <= 1 && y2 <= 1) {
      x1 *= renderedW;
      y1 *= renderedH;
      x2 *= renderedW;
      y2 *= renderedH;
    } else {
      // Pixel coordinates — scale to rendered size
      const scaleX = renderedW / imgSize.w;
      const scaleY = renderedH / imgSize.h;
      x1 *= scaleX;
      y1 *= scaleY;
      x2 *= scaleX;
      y2 *= scaleY;
    }

    overlayStyle = {
      position: "absolute",
      left: `${offsetX + x1}px`,
      top: `${offsetY + y1}px`,
      width: `${x2 - x1}px`,
      height: `${y2 - y1}px`,
      border: `2px solid ${bboxColor}`,
      borderRadius: "4px",
      boxShadow: `0 0 8px ${bboxColor}40, inset 0 0 8px ${bboxColor}10`,
      pointerEvents: "none" as const,
    };

    labelStyle = {
      position: "absolute",
      left: `${offsetX + x1}px`,
      top: `${offsetY + y1 - 28}px`,
      pointerEvents: "none" as const,
    };
  }

  return (
    <div className="relative">
      <div
        ref={containerRef}
        className={`relative bg-black overflow-hidden ${
          isFullscreen
            ? "fixed inset-0 z-50 flex items-center justify-center"
            : "aspect-video"
        }`}
      >
        <img
          ref={imgRef}
          src={src}
          alt="Snapshot del evento"
          className={`${
            isFullscreen ? "max-w-full max-h-full" : "w-full h-full"
          } object-contain`}
          onLoad={updateSizes}
        />

        {/* Bounding Box Overlay */}
        {overlayStyle && (
          <>
            <div style={overlayStyle}>
              {/* Corner accents */}
              <div
                className="absolute -top-[2px] -left-[2px] w-4 h-4"
                style={{
                  borderTop: `3px solid ${bboxColor}`,
                  borderLeft: `3px solid ${bboxColor}`,
                  borderRadius: "4px 0 0 0",
                }}
              />
              <div
                className="absolute -top-[2px] -right-[2px] w-4 h-4"
                style={{
                  borderTop: `3px solid ${bboxColor}`,
                  borderRight: `3px solid ${bboxColor}`,
                  borderRadius: "0 4px 0 0",
                }}
              />
              <div
                className="absolute -bottom-[2px] -left-[2px] w-4 h-4"
                style={{
                  borderBottom: `3px solid ${bboxColor}`,
                  borderLeft: `3px solid ${bboxColor}`,
                  borderRadius: "0 0 0 4px",
                }}
              />
              <div
                className="absolute -bottom-[2px] -right-[2px] w-4 h-4"
                style={{
                  borderBottom: `3px solid ${bboxColor}`,
                  borderRight: `3px solid ${bboxColor}`,
                  borderRadius: "0 0 4px 0",
                }}
              />
            </div>

            {/* Label tag above bbox */}
            {labelStyle && (
              <div style={labelStyle}>
                <div
                  className="flex items-center gap-1.5 px-2 py-1 rounded-t-md text-white text-xs font-semibold whitespace-nowrap"
                  style={{ backgroundColor: bboxColor }}
                >
                  <span>{personName || LABEL_NAMES[label] || label}</span>
                  <span className="opacity-80">
                    {Math.round(confidence * 100)}%
                  </span>
                  {trackerId && !personName && (
                    <span className="opacity-60">#{trackerId}</span>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* Fullscreen toggle */}
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          className="absolute top-3 right-3 p-2 bg-black/60 hover:bg-black/80 rounded-lg transition-colors z-10"
        >
          <Maximize2 className="w-4 h-4 text-white" />
        </button>

        {/* ESC to close fullscreen */}
        {isFullscreen && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-black/60 rounded-full text-white/60 text-xs">
            Presiona ESC o haz click para cerrar
          </div>
        )}
      </div>

      {/* Close fullscreen on click */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-40 bg-black/90"
          onClick={() => setIsFullscreen(false)}
        />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/* Main page                                                      */
/* ═══════════════════════════════════════════════════════════════ */

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

  // ESC to close fullscreen
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // close any fullscreen
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-text-muted">Cargando evento...</div>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <AlertTriangle className="w-12 h-12 text-warning" />
        <p className="text-text-muted">Evento no encontrado</p>
        <button
          onClick={() => router.back()}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
        >
          Volver
        </button>
      </div>
    );
  }

  const eventInfo =
    EVENT_TYPE_INFO[event.event_type] || EVENT_TYPE_INFO.object_detected;
  const attrs = event.attributes || {};
  const hasPersonAttrs =
    event.label === "person" && Object.values(attrs).some(Boolean);
  const hasVehicleAttrs =
    ["car", "truck", "bus", "motorcycle"].includes(event.label) &&
    Object.values(attrs).some(Boolean);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-lg hover:bg-surface-hover transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-text-secondary" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
              <span className="text-2xl">{eventInfo.icon}</span>
              {eventInfo.label}
            </h1>
            <p className="text-text-muted text-sm">
              {formatDate(event.detected_at)}
            </p>
          </div>
        </div>

        {/* Confidence badge */}
        <div
          className="px-3 py-1.5 rounded-full text-white text-sm font-bold"
          style={{ backgroundColor: eventInfo.color }}
        >
          {Math.round(event.confidence * 100)}% confianza
        </div>
      </div>

      {/* ── Alert reason banner ── */}
      <div
        className="rounded-xl p-4 flex items-start gap-3"
        style={{
          backgroundColor: `${eventInfo.color}15`,
          border: `1px solid ${eventInfo.color}30`,
        }}
      >
        <AlertTriangle
          className="w-5 h-5 mt-0.5 flex-shrink-0"
          style={{ color: eventInfo.color }}
        />
        <div>
          <p className="text-text-primary font-semibold text-sm">
            Por que se genero esta alerta?
          </p>
          <p className="text-text-secondary text-sm mt-1">{eventInfo.reason}</p>
          <div className="flex flex-wrap gap-3 mt-2">
            <span className="inline-flex items-center gap-1 text-xs text-text-muted">
              <Target className="w-3 h-3" />
              {LABEL_NAMES[event.label] || event.label} detectado con{" "}
              {Math.round(event.confidence * 100)}% de confianza
            </span>
            {event.tracker_id && (
              <span className="inline-flex items-center gap-1 text-xs text-text-muted">
                <Eye className="w-3 h-3" />
                Rastreado como objeto #{event.tracker_id}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Snapshot with overlay (2 cols) ── */}
        <div className="lg:col-span-2 bg-surface border border-border rounded-xl overflow-hidden">
          {event.snapshot_url ? (
            <SnapshotWithOverlay
              snapshotUrl={event.snapshot_url}
              bbox={event.bbox}
              label={event.label}
              confidence={event.confidence}
              eventType={event.event_type}
              trackerId={event.tracker_id}
              personName={attrs.face_match || undefined}
            />
          ) : (
            <div className="aspect-video bg-background flex items-center justify-center">
              <div className="text-center text-text-muted">
                <Image className="w-12 h-12 mx-auto mb-2" />
                <p className="text-sm">Sin snapshot disponible</p>
              </div>
            </div>
          )}

          {/* Video clip button */}
          {event.clip_url && (
            <div className="p-3 border-t border-border">
              <button className="flex items-center gap-2 text-sm text-primary hover:text-primary-hover transition-colors">
                <Video className="w-4 h-4" />
                Ver clip de video
              </button>
            </div>
          )}
        </div>

        {/* ── Sidebar details (1 col) ── */}
        <div className="space-y-4">
          {/* What was detected */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Shield className="w-4 h-4" style={{ color: eventInfo.color }} />
              Que se detecto
            </h2>

            <div className="space-y-3">
              <DetailRow
                label="Objeto"
                value={LABEL_NAMES[event.label] || event.label}
                highlight
                color={eventInfo.color}
              />
              <DetailRow
                label="Tipo de evento"
                value={eventInfo.label}
              />
              <DetailRow
                label="Confianza"
                value={`${Math.round(event.confidence * 100)}%`}
              />
              {event.tracker_id && (
                <DetailRow
                  label="ID de rastreo"
                  value={`#${event.tracker_id}`}
                />
              )}
            </div>
          </div>

          {/* Person Identification */}
          {event.label === "person" && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                {attrs.face_match && !attrs.face_match.startsWith("Desconocido") ? (
                  <>
                    <span className="w-4 h-4 text-green-400">👤</span>
                    Persona identificada
                  </>
                ) : attrs.face_match ? (
                  <>
                    <span className="w-4 h-4 text-orange-400">❓</span>
                    Persona desconocida
                  </>
                ) : (
                  <>
                    <span className="w-4 h-4 text-text-muted">👤</span>
                    Identificacion facial
                  </>
                )}
              </h2>

              <div className="space-y-3">
                {attrs.face_match ? (
                  <>
                    <DetailRow
                      label="Nombre"
                      value={attrs.face_match}
                      highlight
                      color={attrs.face_match.startsWith("Desconocido") ? "#f97316" : "#22c55e"}
                    />
                    {attrs.match_distance !== undefined && (
                      <DetailRow
                        label="Distancia"
                        value={`${attrs.match_distance.toFixed(4)}`}
                      />
                    )}
                  </>
                ) : attrs.face_detected ? (
                  <DetailRow
                    label="Rostro"
                    value="Detectado — No coincide"
                    highlight
                    color="#f59e0b"
                  />
                ) : (
                  <DetailRow
                    label="Rostro"
                    value="No detectado"
                  />
                )}

                {attrs.edad_estimada && (
                  <DetailRow label="Edad estimada" value={attrs.edad_estimada} />
                )}
                {attrs.genero_estimado && (
                  <DetailRow label="Genero estimado" value={attrs.genero_estimado} />
                )}
                {attrs.emocion && (
                  <DetailRow label="Emocion" value={attrs.emocion} />
                )}

                {event.person_id && (
                  <div className="pt-2 border-t border-border">
                    <a
                      href={`/dashboard/database`}
                      className="text-xs text-primary hover:text-primary-hover transition-colors"
                    >
                      Ver en base de datos →
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* When & Where */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Clock className="w-4 h-4 text-text-muted" />
              Cuando y donde
            </h2>

            <div className="space-y-3">
              <DetailRow
                label="Fecha y hora"
                value={formatDate(event.detected_at)}
              />
              <DetailRow
                label="Camara"
                value={event.camera_id ? event.camera_id.slice(0, 8) + "..." : "N/A"}
              />
              {event.zone_id && (
                <DetailRow
                  label="Zona"
                  value={event.zone_id.slice(0, 8) + "..."}
                />
              )}
            </div>
          </div>

          {/* Review status */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Eye className="w-4 h-4 text-text-muted" />
              Estado de revision
            </h2>

            <div className="space-y-3">
              <DetailRow label="Revision" value={event.review_pass === "online" ? "En linea" : event.review_pass} />
              <DetailRow
                label="Revision profunda"
                value={event.needs_deep_review ? "Pendiente" : "Completado"}
                highlight={event.needs_deep_review}
                color="#f59e0b"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Attributes section ── */}
      {(hasPersonAttrs || hasVehicleAttrs) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Person Attributes */}
          {hasPersonAttrs && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <User className="w-4 h-4 text-success" />
                Atributos de persona
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {attrs.ropa_sup_color && (
                  <DetailRow
                    label="Ropa superior"
                    value={`${attrs.ropa_sup_tipo || ""} ${attrs.ropa_sup_color}`.trim()}
                  />
                )}
                {attrs.ropa_inf_color && (
                  <DetailRow
                    label="Ropa inferior"
                    value={`${attrs.ropa_inf_tipo || ""} ${attrs.ropa_inf_color}`.trim()}
                  />
                )}
                {attrs.casco !== undefined && attrs.casco !== null && (
                  <DetailRow label="Casco" value={attrs.casco ? "Si" : "No"} />
                )}
                {attrs.chaleco !== undefined && attrs.chaleco !== null && (
                  <DetailRow
                    label="Chaleco"
                    value={attrs.chaleco ? "Si" : "No"}
                  />
                )}
                {attrs.genero_estimado && (
                  <DetailRow
                    label="Genero estimado"
                    value={attrs.genero_estimado}
                  />
                )}
                {attrs.edad_estimada && (
                  <DetailRow
                    label="Edad estimada"
                    value={attrs.edad_estimada}
                  />
                )}
              </div>
            </div>
          )}

          {/* Vehicle Attributes */}
          {hasVehicleAttrs && (
            <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Car className="w-4 h-4 text-primary" />
                Atributos de vehiculo
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {attrs.tipo_vehiculo && (
                  <DetailRow label="Tipo" value={attrs.tipo_vehiculo} />
                )}
                {attrs.color_vehiculo && (
                  <DetailRow label="Color" value={attrs.color_vehiculo} />
                )}
                {attrs.placa_texto && (
                  <DetailRow
                    label="Placa"
                    value={attrs.placa_texto}
                    highlight
                    color="#3b82f6"
                  />
                )}
                {attrs.marca_estimada && (
                  <DetailRow label="Marca" value={attrs.marca_estimada} />
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Bounding Box coordinates (collapsible) ── */}
      {event.bbox && (
        <details className="bg-surface border border-border rounded-xl overflow-hidden">
          <summary className="p-4 cursor-pointer text-sm font-semibold text-text-secondary hover:text-text-primary transition-colors flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            Coordenadas del bounding box
          </summary>
          <div className="px-4 pb-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-background rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted">X1 (izquierda)</p>
                <p className="text-sm font-mono text-text-primary mt-1">
                  {typeof event.bbox.x1 === "number"
                    ? event.bbox.x1.toFixed(1)
                    : event.bbox.x1}
                </p>
              </div>
              <div className="bg-background rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted">Y1 (arriba)</p>
                <p className="text-sm font-mono text-text-primary mt-1">
                  {typeof event.bbox.y1 === "number"
                    ? event.bbox.y1.toFixed(1)
                    : event.bbox.y1}
                </p>
              </div>
              <div className="bg-background rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted">X2 (derecha)</p>
                <p className="text-sm font-mono text-text-primary mt-1">
                  {typeof event.bbox.x2 === "number"
                    ? event.bbox.x2.toFixed(1)
                    : event.bbox.x2}
                </p>
              </div>
              <div className="bg-background rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted">Y2 (abajo)</p>
                <p className="text-sm font-mono text-text-primary mt-1">
                  {typeof event.bbox.y2 === "number"
                    ? event.bbox.y2.toFixed(1)
                    : event.bbox.y2}
                </p>
              </div>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/* Detail row component                                           */
/* ═══════════════════════════════════════════════════════════════ */

function DetailRow({
  label,
  value,
  highlight,
  color,
}: {
  label: string;
  value: any;
  highlight?: boolean;
  color?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <p className="text-xs text-text-muted">{label}</p>
      {highlight && color ? (
        <span
          className="text-sm font-semibold px-2 py-0.5 rounded"
          style={{
            color: color,
            backgroundColor: `${color}15`,
          }}
        >
          {String(value)}
        </span>
      ) : (
        <p className="text-sm text-text-primary capitalize">{String(value)}</p>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  AlertTriangle,
  Plus,
  Bell,
  Mail,
  MessageSquare,
  Globe,
  ToggleLeft,
  ToggleRight,
  TestTube,
} from "lucide-react";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    loadAlerts();
  }, []);

  async function loadAlerts() {
    try {
      const data = await api.getAlerts();
      setAlerts(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const actionIcons: Record<string, any> = {
    email: Mail,
    webhook: Globe,
    whatsapp: MessageSquare,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Alertas</h1>
          <p className="text-text-muted text-sm mt-1">
            Reglas de notificacion automatica
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nueva Regla
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-pulse text-text-muted">Cargando...</div>
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-surface border border-border rounded-xl">
          <AlertTriangle className="w-12 h-12 text-text-muted mb-3" />
          <p className="text-text-secondary">Sin reglas de alerta</p>
          <p className="text-xs text-text-muted mt-1">
            Crea una regla para recibir notificaciones
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className="bg-surface border border-border rounded-xl p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center mt-0.5">
                    <Bell className="w-5 h-5 text-warning" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text-primary">
                      {alert.name}
                    </h3>
                    <p className="text-xs text-text-muted mt-0.5">
                      Evento: {alert.event_type} | Cooldown:{" "}
                      {alert.cooldown_seconds}s
                    </p>
                    {alert.last_triggered_at && (
                      <p className="text-xs text-text-muted mt-1">
                        Ultima activacion: {formatDate(alert.last_triggered_at)}
                      </p>
                    )}
                    {/* Actions */}
                    <div className="flex items-center gap-2 mt-2">
                      {(Array.isArray(alert.actions)
                        ? alert.actions
                        : [alert.actions]
                      ).map((action: any, i: number) => {
                        const Icon =
                          actionIcons[action.type] || Globe;
                        return (
                          <span
                            key={i}
                            className="flex items-center gap-1 text-xs text-text-secondary bg-background px-2 py-1 rounded"
                          >
                            <Icon className="w-3 h-3" />
                            {action.type}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="p-2 rounded-lg hover:bg-surface-hover text-text-muted hover:text-accent transition-colors">
                    <TestTube className="w-4 h-4" />
                  </button>
                  {alert.enabled ? (
                    <ToggleRight className="w-8 h-8 text-success cursor-pointer" />
                  ) : (
                    <ToggleLeft className="w-8 h-8 text-text-muted cursor-pointer" />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Alert Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-lg">
            <h2 className="text-lg font-bold text-text-primary mb-4">
              Nueva Regla de Alerta
            </h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const form = e.target as HTMLFormElement;
                const data = new FormData(form);
                try {
                  await api.createAlert({
                    name: data.get("name"),
                    event_type: data.get("event_type"),
                    actions: [{ type: data.get("action_type"), to: data.get("action_to") }],
                    cooldown_seconds: parseInt(data.get("cooldown") as string) || 60,
                  });
                  setShowAdd(false);
                  loadAlerts();
                } catch (err) {
                  console.error(err);
                }
              }}
              className="space-y-3"
            >
              <input name="name" placeholder="Nombre de la regla" required className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary" />
              <select name="event_type" required className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary">
                <option value="person_detected">Persona detectada</option>
                <option value="vehicle_detected">Vehiculo detectado</option>
                <option value="zone_crossing">Cruce de zona</option>
                <option value="overcrowding">Aglomeracion</option>
              </select>
              <select name="action_type" required className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary">
                <option value="email">Email</option>
                <option value="webhook">Webhook</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
              <input name="action_to" placeholder="Destinatario (email, URL...)" className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary" />
              <input name="cooldown" type="number" defaultValue={60} placeholder="Cooldown (segundos)" className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary" />
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary">Cancelar</button>
                <button type="submit" className="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg">Crear</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

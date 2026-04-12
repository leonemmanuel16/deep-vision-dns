"use client";

import { useState } from "react";
import {
  Settings,
  Video,
  Users,
  Mail,
  Globe,
  Trash2,
  Languages,
  Server,
} from "lucide-react";

const tabs = [
  { key: "streaming", label: "Streaming", icon: Video },
  { key: "users", label: "Usuarios", icon: Users },
  { key: "email", label: "Email/SMTP", icon: Mail },
  { key: "network", label: "Red/DDNS", icon: Globe },
  { key: "trash", label: "Papelera", icon: Trash2 },
  { key: "language", label: "Idioma", icon: Languages },
  { key: "system", label: "Sistema", icon: Server },
] as const;

type Tab = (typeof tabs)[number]["key"];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("streaming");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Configuracion</h1>
        <p className="text-text-muted text-sm mt-1">
          Ajustes del sistema Deep Vision
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar Tabs */}
        <div className="w-48 shrink-0 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeTab === tab.key
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-hover"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 bg-surface border border-border rounded-xl p-6">
          {activeTab === "streaming" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Configuracion de Streaming
              </h2>
              <SettingField label="FPS de Deteccion" type="number" defaultValue="10" />
              <SettingField label="Threshold de Confianza" type="number" defaultValue="0.5" />
              <SettingField label="Motion ON Threshold (%)" type="number" defaultValue="0.5" />
              <SettingField label="Motion OFF Frames" type="number" defaultValue="30" />
              <SettingField label="Retencion de Video (horas)" type="number" defaultValue="48" />
            </div>
          )}

          {activeTab === "users" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Gestion de Usuarios
              </h2>
              <p className="text-text-muted text-sm">
                Administra usuarios y permisos desde aqui.
              </p>
            </div>
          )}

          {activeTab === "email" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Configuracion SMTP
              </h2>
              <SettingField label="SMTP Host" defaultValue="" placeholder="smtp.gmail.com" />
              <SettingField label="SMTP Port" type="number" defaultValue="587" />
              <SettingField label="SMTP User" defaultValue="" placeholder="tu@email.com" />
              <SettingField label="SMTP Password" type="password" defaultValue="" />
              <SettingField label="From" defaultValue="" placeholder="alertas@tudominio.com" />
            </div>
          )}

          {activeTab === "network" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Red / DDNS
              </h2>
              <p className="text-text-muted text-sm">
                Configuracion de red y DNS dinamico — proximamente.
              </p>
            </div>
          )}

          {activeTab === "trash" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Papelera
              </h2>
              <p className="text-text-muted text-sm">
                Elementos eliminados recientemente — proximamente.
              </p>
            </div>
          )}

          {activeTab === "language" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Idioma
              </h2>
              <select className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-primary">
                <option value="es">Espanol</option>
                <option value="en">English</option>
              </select>
            </div>
          )}

          {activeTab === "system" && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-text-primary">
                Sistema
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-text-muted">Version</span>
                  <span className="text-text-primary">1.0.0</span>
                </div>
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-text-muted">DeepStream</span>
                  <span className="text-text-primary">7.1</span>
                </div>
                <div className="flex justify-between py-2 border-b border-border/50">
                  <span className="text-text-muted">CUDA</span>
                  <span className="text-text-primary">12.4</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-text-muted">Modelo</span>
                  <span className="text-text-primary">YOLOv8m (TensorRT FP16)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingField({
  label,
  type = "text",
  defaultValue,
  placeholder,
}: {
  label: string;
  type?: string;
  defaultValue?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-text-muted mb-1">{label}</label>
      <input
        type={type}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="w-full max-w-sm px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
      />
    </div>
  );
}

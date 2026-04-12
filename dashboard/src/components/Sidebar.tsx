"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Camera,
  Bell,
  Calendar,
  AlertTriangle,
  Flame,
  ArrowRightLeft,
  Users,
  Activity,
  Settings,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/cameras", label: "Camaras", icon: Camera },
  { href: "/dashboard/events", label: "Eventos", icon: Bell },
  { href: "/dashboard/recordings", label: "Grabaciones", icon: Calendar },
  { href: "/dashboard/alerts", label: "Alertas", icon: AlertTriangle },
  { href: "/dashboard/heatmap", label: "Mapa de Calor", icon: Flame },
  { href: "/dashboard/traffic", label: "Trafico", icon: ArrowRightLeft },
  { href: "/dashboard/database", label: "Personas", icon: Users },
  { href: "/dashboard/health", label: "Sistema", icon: Activity },
  { href: "/dashboard/settings", label: "Configuracion", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 bg-surface border-r border-border flex flex-col z-50">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-border">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-text-primary">Deep Vision</h1>
          <p className="text-[10px] text-text-muted">by DNS</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-hover"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t border-border">
        <button
          onClick={() => api.logout()}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text-secondary hover:text-danger hover:bg-danger/5 transition-all w-full"
        >
          <LogOut className="w-4 h-4" />
          <span>Cerrar sesion</span>
        </button>
      </div>
    </aside>
  );
}

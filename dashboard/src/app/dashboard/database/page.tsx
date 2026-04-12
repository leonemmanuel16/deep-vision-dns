"use client";

import { useState } from "react";
import { Users, Plus, Search, User, Trash2 } from "lucide-react";

export default function DatabasePage() {
  const [searchQuery, setSearchQuery] = useState("");

  // Sample data — in production comes from API
  const persons: any[] = [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Base de Datos de Personas
          </h1>
          <p className="text-text-muted text-sm mt-1">
            Personas registradas para reconocimiento facial
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
          Agregar Persona
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          placeholder="Buscar por nombre o ID..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
        />
      </div>

      {/* Persons Grid */}
      {persons.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-surface border border-border rounded-xl">
          <Users className="w-12 h-12 text-text-muted mb-3" />
          <p className="text-text-secondary">Sin personas registradas</p>
          <p className="text-xs text-text-muted mt-1">
            Agrega personas para habilitar reconocimiento facial
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {persons.map((person: any) => (
            <div
              key={person.id}
              className="bg-surface border border-border rounded-xl p-4 hover:border-border-hover transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-full bg-background flex items-center justify-center">
                  <User className="w-6 h-6 text-text-muted" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-text-primary truncate">
                    {person.name}
                  </h3>
                  <p className="text-xs text-text-muted">{person.department}</p>
                  <p className="text-xs text-text-muted">
                    ID: {person.employee_id}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

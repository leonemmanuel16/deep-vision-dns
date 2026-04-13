"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Users,
  Plus,
  Search,
  User,
  Trash2,
  Upload,
  X,
  Check,
  Camera,
  Shield,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";

interface Person {
  id: string;
  name: string;
  employee_id: string | null;
  department: string | null;
  photo_url: string | null;
  notes: string | null;
  is_active: boolean;
  has_face_encoding: boolean;
  created_at: string;
  updated_at: string;
}

interface PersonStats {
  total: number;
  active: number;
  with_face_encoding: number;
  without_face_encoding: number;
}

export default function DatabasePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [persons, setPersons] = useState<Person[]>([]);
  const [stats, setStats] = useState<PersonStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (searchQuery) params.search = searchQuery;
      const [personsData, statsData] = await Promise.all([
        api.getPersons(params),
        api.getPersonStats(),
      ]);
      setPersons(personsData);
      setStats(statsData);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDelete = async (id: string) => {
    try {
      await api.deletePerson(id);
      setDeleteConfirm(null);
      loadData();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Base de Datos de Personas
          </h1>
          <p className="text-text-muted text-sm mt-1">
            Personas registradas para reconocimiento facial
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Agregar Persona
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-text-primary">{stats.total}</p>
            <p className="text-xs text-text-muted">Total registradas</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-green-500">{stats.active}</p>
            <p className="text-xs text-text-muted">Activas</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-blue-500">{stats.with_face_encoding}</p>
            <p className="text-xs text-text-muted">Con rostro registrado</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-orange-500">{stats.without_face_encoding}</p>
            <p className="text-xs text-text-muted">Sin rostro</p>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          placeholder="Buscar por nombre, ID o departamento..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-9 pr-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
          <AlertCircle className="w-4 h-4" />
          {error}
          <button onClick={() => setError("")} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Persons Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : persons.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 bg-surface border border-border rounded-xl">
          <Users className="w-12 h-12 text-text-muted mb-3" />
          <p className="text-text-secondary">Sin personas registradas</p>
          <p className="text-xs text-text-muted mt-1">
            Agrega personas para habilitar reconocimiento facial
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {persons.map((person) => (
            <div
              key={person.id}
              className="bg-surface border border-border rounded-xl p-4 hover:border-border-hover transition-colors relative group"
            >
              <div className="flex items-start gap-3">
                <div className="w-14 h-14 rounded-full bg-background flex items-center justify-center overflow-hidden flex-shrink-0">
                  {person.photo_url ? (
                    <img
                      src={`${process.env.NEXT_PUBLIC_API_URL}/api/snapshots/${person.photo_url}`}
                      alt={person.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <User className="w-7 h-7 text-text-muted" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-text-primary truncate">
                    {person.name}
                  </h3>
                  {person.department && (
                    <p className="text-xs text-text-muted">{person.department}</p>
                  )}
                  {person.employee_id && (
                    <p className="text-xs text-text-muted">
                      ID: {person.employee_id}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    {person.has_face_encoding ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-500/10 text-green-400">
                        <Shield className="w-3 h-3" />
                        Rostro registrado
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-500/10 text-orange-400">
                        <Camera className="w-3 h-3" />
                        Sin rostro
                      </span>
                    )}
                    {!person.is_active && (
                      <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-500/10 text-red-400">
                        Inactivo
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Delete button */}
              <button
                onClick={() => setDeleteConfirm(person.id)}
                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-red-500/10 text-text-muted hover:text-red-400"
              >
                <Trash2 className="w-4 h-4" />
              </button>

              {/* Delete confirmation */}
              {deleteConfirm === person.id && (
                <div className="absolute inset-0 bg-surface/95 rounded-xl flex flex-col items-center justify-center gap-3 p-4">
                  <p className="text-sm text-text-primary text-center">
                    Eliminar a <strong>{person.name}</strong>?
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(person.id)}
                      className="px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs rounded-lg"
                    >
                      Eliminar
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="px-3 py-1.5 bg-surface border border-border hover:border-border-hover text-text-primary text-xs rounded-lg"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add Person Modal */}
      {showAddModal && (
        <AddPersonModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}

function AddPersonModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [department, setDepartment] = useState("");
  const [notes, setNotes] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setPhoto(file);
      const reader = new FileReader();
      reader.onload = (ev) => setPhotoPreview(ev.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("El nombre es requerido");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      if (photo) {
        // Register with photo (face embedding will be extracted)
        const formData = new FormData();
        formData.append("name", name.trim());
        if (employeeId) formData.append("employee_id", employeeId.trim());
        if (department) formData.append("department", department.trim());
        if (notes) formData.append("notes", notes.trim());
        formData.append("photo", photo);

        await api.registerPersonWithPhoto(formData);
      } else {
        // Create without photo
        await api.createPerson({
          name: name.trim(),
          employee_id: employeeId.trim() || undefined,
          department: department.trim() || undefined,
          notes: notes.trim() || undefined,
        });
      }
      onSuccess();
    } catch (e: any) {
      setError(e.message || "Error al registrar persona");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-lg p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-text-primary">
            Registrar Persona
          </h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Photo upload */}
        <div className="flex flex-col items-center gap-3">
          <div
            onClick={() => fileInputRef.current?.click()}
            className="w-28 h-28 rounded-full bg-background border-2 border-dashed border-border hover:border-primary flex items-center justify-center cursor-pointer overflow-hidden transition-colors"
          >
            {photoPreview ? (
              <img
                src={photoPreview}
                alt="Preview"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center text-text-muted">
                <Camera className="w-8 h-8 mb-1" />
                <span className="text-[10px]">Subir foto</span>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handlePhotoChange}
            className="hidden"
          />
          <p className="text-xs text-text-muted text-center">
            {photo
              ? "La foto debe mostrar el rostro claramente"
              : "Sube una foto con el rostro visible para reconocimiento facial"}
          </p>
        </div>

        {/* Form fields */}
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-muted mb-1">
              Nombre *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nombre completo"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">
                ID Empleado
              </label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="EMP-001"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">
                Departamento
              </label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="Seguridad"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Notas</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notas adicionales..."
              rows={2}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary resize-none"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {submitting ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            {photo ? "Registrar con Rostro" : "Registrar sin Foto"}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 bg-background border border-border hover:border-border-hover text-text-primary text-sm rounded-lg transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

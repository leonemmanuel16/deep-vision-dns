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
  UserCheck,
  UserX,
  Link,
  Eye,
  Clock,
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
  is_unknown: boolean;
  has_face_encoding: boolean;
  first_seen_camera_id: string | null;
  first_seen_at: string | null;
  times_seen: number;
  last_seen_at: string | null;
  merged_into_id: string | null;
  created_at: string;
  updated_at: string;
}

interface PersonStats {
  total: number;
  active: number;
  known: number;
  unknowns: number;
  with_face_encoding: number;
  without_face_encoding: number;
}

type TabType = "known" | "unknown";

export default function DatabasePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("known");
  const [persons, setPersons] = useState<Person[]>([]);
  const [stats, setStats] = useState<PersonStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [identifyPerson, setIdentifyPerson] = useState<Person | null>(null);
  const [mergePerson, setMergePerson] = useState<Person | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (searchQuery) params.search = searchQuery;
      if (activeTab === "unknown") params.is_unknown = "true";
      if (activeTab === "known") params.is_unknown = "false";

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
  }, [searchQuery, activeTab]);

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

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const d = new Date(dateStr);
    return d.toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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
            Reconocimiento facial con DeepFace (RetinaFace + ArcFace)
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
            <p className="text-2xl font-bold text-green-500">{stats.known}</p>
            <p className="text-xs text-text-muted">Identificadas</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-orange-500">{stats.unknowns}</p>
            <p className="text-xs text-text-muted">Desconocidos</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-blue-500">
              {stats.with_face_encoding}
            </p>
            <p className="text-xs text-text-muted">Con rostro registrado</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-background p-1 rounded-lg w-fit">
        <button
          onClick={() => setActiveTab("known")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            activeTab === "known"
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          <UserCheck className="w-4 h-4" />
          Identificadas
          {stats && (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-green-500/10 text-green-400 rounded-full">
              {stats.known}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("unknown")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            activeTab === "unknown"
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          <UserX className="w-4 h-4" />
          Desconocidos
          {stats && stats.unknowns > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-orange-500/10 text-orange-400 rounded-full animate-pulse">
              {stats.unknowns}
            </span>
          )}
        </button>
      </div>

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
          {activeTab === "unknown" ? (
            <>
              <UserX className="w-12 h-12 text-text-muted mb-3" />
              <p className="text-text-secondary">Sin personas desconocidas</p>
              <p className="text-xs text-text-muted mt-1">
                Los rostros no identificados aparecen aqui automaticamente
              </p>
            </>
          ) : (
            <>
              <Users className="w-12 h-12 text-text-muted mb-3" />
              <p className="text-text-secondary">Sin personas registradas</p>
              <p className="text-xs text-text-muted mt-1">
                Agrega personas para habilitar reconocimiento facial
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {persons.map((person) => (
            <PersonCard
              key={person.id}
              person={person}
              formatDate={formatDate}
              onDelete={() => setDeleteConfirm(person.id)}
              onIdentify={() => setIdentifyPerson(person)}
              onMerge={() => setMergePerson(person)}
              deleteConfirm={deleteConfirm === person.id}
              onCancelDelete={() => setDeleteConfirm(null)}
              onConfirmDelete={() => handleDelete(person.id)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AddPersonModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            loadData();
          }}
        />
      )}

      {identifyPerson && (
        <IdentifyModal
          person={identifyPerson}
          onClose={() => setIdentifyPerson(null)}
          onSuccess={() => {
            setIdentifyPerson(null);
            loadData();
          }}
        />
      )}

      {mergePerson && (
        <MergeModal
          person={mergePerson}
          onClose={() => setMergePerson(null)}
          onSuccess={() => {
            setMergePerson(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Person Card Component
// ═══════════════════════════════════════════════════════════════

function PersonCard({
  person,
  formatDate,
  onDelete,
  onIdentify,
  onMerge,
  deleteConfirm,
  onCancelDelete,
  onConfirmDelete,
}: {
  person: Person;
  formatDate: (d: string | null) => string;
  onDelete: () => void;
  onIdentify: () => void;
  onMerge: () => void;
  deleteConfirm: boolean;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const photoSrc = person.photo_url
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/snapshots/${person.photo_url}`
    : null;

  return (
    <div className="bg-surface border border-border rounded-xl p-4 hover:border-border-hover transition-colors relative group">
      <div className="flex items-start gap-3">
        <div className="w-14 h-14 rounded-full bg-background flex items-center justify-center overflow-hidden flex-shrink-0 border-2 border-border">
          {photoSrc ? (
            <img
              src={photoSrc}
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
            <p className="text-xs text-text-muted">ID: {person.employee_id}</p>
          )}

          {/* Status badges */}
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            {person.is_unknown ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-500/10 text-orange-400">
                <UserX className="w-3 h-3" />
                Desconocido
              </span>
            ) : person.has_face_encoding ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-500/10 text-green-400">
                <Shield className="w-3 h-3" />
                Identificado
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-500/10 text-gray-400">
                <Camera className="w-3 h-3" />
                Sin rostro
              </span>
            )}
          </div>

          {/* Times seen + last seen for unknowns */}
          {person.is_unknown && (
            <div className="mt-2 space-y-0.5">
              <p className="text-[10px] text-text-muted flex items-center gap-1">
                <Eye className="w-3 h-3" />
                Visto {person.times_seen} {person.times_seen === 1 ? "vez" : "veces"}
              </p>
              {person.last_seen_at && (
                <p className="text-[10px] text-text-muted flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDate(person.last_seen_at)}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {person.is_unknown && (
          <>
            <button
              onClick={onIdentify}
              title="Asignar nombre"
              className="p-1.5 rounded-lg hover:bg-green-500/10 text-text-muted hover:text-green-400"
            >
              <UserCheck className="w-4 h-4" />
            </button>
            <button
              onClick={onMerge}
              title="Vincular a persona existente"
              className="p-1.5 rounded-lg hover:bg-blue-500/10 text-text-muted hover:text-blue-400"
            >
              <Link className="w-4 h-4" />
            </button>
          </>
        )}
        <button
          onClick={onDelete}
          title="Eliminar"
          className="p-1.5 rounded-lg hover:bg-red-500/10 text-text-muted hover:text-red-400"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Delete confirmation overlay */}
      {deleteConfirm && (
        <div className="absolute inset-0 bg-surface/95 rounded-xl flex flex-col items-center justify-center gap-3 p-4 z-10">
          <p className="text-sm text-text-primary text-center">
            Eliminar a <strong>{person.name}</strong>?
          </p>
          <div className="flex gap-2">
            <button
              onClick={onConfirmDelete}
              className="px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs rounded-lg"
            >
              Eliminar
            </button>
            <button
              onClick={onCancelDelete}
              className="px-3 py-1.5 bg-surface border border-border hover:border-border-hover text-text-primary text-xs rounded-lg"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Add Person Modal
// ═══════════════════════════════════════════════════════════════

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
        const formData = new FormData();
        formData.append("name", name.trim());
        if (employeeId) formData.append("employee_id", employeeId.trim());
        if (department) formData.append("department", department.trim());
        if (notes) formData.append("notes", notes.trim());
        formData.append("photo", photo);
        await api.registerPersonWithPhoto(formData);
      } else {
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

        <div className="flex flex-col items-center gap-3">
          <div
            onClick={() => fileInputRef.current?.click()}
            className="w-28 h-28 rounded-full bg-background border-2 border-dashed border-border hover:border-primary flex items-center justify-center cursor-pointer overflow-hidden transition-colors"
          >
            {photoPreview ? (
              <img src={photoPreview} alt="Preview" className="w-full h-full object-cover" />
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
            La foto debe mostrar el rostro claramente
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-muted mb-1">Nombre *</label>
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
              <label className="block text-xs text-text-muted mb-1">ID Empleado</label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="EMP-001"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Departamento</label>
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

// ═══════════════════════════════════════════════════════════════
// Identify Unknown Modal
// ═══════════════════════════════════════════════════════════════

function IdentifyModal({
  person,
  onClose,
  onSuccess,
}: {
  person: Person;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [department, setDepartment] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const photoSrc = person.photo_url
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/snapshots/${person.photo_url}`
    : null;

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("El nombre es requerido");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api.identifyPerson(person.id, {
        name: name.trim(),
        employee_id: employeeId.trim() || undefined,
        department: department.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onSuccess();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-lg p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-text-primary">
            Identificar Persona
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

        {/* Show the unknown person's face */}
        <div className="flex items-center gap-4 p-3 bg-background rounded-lg border border-border">
          <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center overflow-hidden border-2 border-orange-500/30">
            {photoSrc ? (
              <img src={photoSrc} alt="Desconocido" className="w-full h-full object-cover" />
            ) : (
              <UserX className="w-8 h-8 text-orange-400" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-text-primary">{person.name}</p>
            <p className="text-xs text-text-muted">
              Visto {person.times_seen} {person.times_seen === 1 ? "vez" : "veces"}
            </p>
            <p className="text-xs text-orange-400">Asignar identidad real</p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-muted mb-1">Nombre real *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nombre completo de la persona"
              autoFocus
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">ID Empleado</label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="EMP-001"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Departamento</label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="Seguridad"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
              />
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleSubmit}
            disabled={submitting || !name.trim()}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {submitting ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <UserCheck className="w-4 h-4" />
            )}
            Identificar
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

// ═══════════════════════════════════════════════════════════════
// Merge Modal — link unknown to existing person
// ═══════════════════════════════════════════════════════════════

function MergeModal({
  person,
  onClose,
  onSuccess,
}: {
  person: Person;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [knownPersons, setKnownPersons] = useState<Person[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTarget, setSelectedTarget] = useState<Person | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadKnown = async () => {
      try {
        const params: Record<string, string> = { is_unknown: "false" };
        if (searchQuery) params.search = searchQuery;
        const data = await api.getPersons(params);
        setKnownPersons(data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    loadKnown();
  }, [searchQuery]);

  const handleMerge = async () => {
    if (!selectedTarget) return;
    setSubmitting(true);
    setError("");
    try {
      await api.mergePersons(person.id, selectedTarget.id);
      onSuccess();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const photoSrc = person.photo_url
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/snapshots/${person.photo_url}`
    : null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-lg p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-text-primary">
            Vincular a Persona Existente
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

        {/* Source unknown person */}
        <div className="flex items-center gap-4 p-3 bg-orange-500/5 rounded-lg border border-orange-500/20">
          <div className="w-14 h-14 rounded-full bg-surface flex items-center justify-center overflow-hidden border-2 border-orange-500/30 flex-shrink-0">
            {photoSrc ? (
              <img src={photoSrc} alt="Desconocido" className="w-full h-full object-cover" />
            ) : (
              <UserX className="w-7 h-7 text-orange-400" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-text-primary">{person.name}</p>
            <p className="text-xs text-orange-400">
              Se fusionara con la persona seleccionada abajo
            </p>
          </div>
        </div>

        <div className="flex items-center justify-center">
          <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
            <Link className="w-4 h-4 text-blue-400" />
          </div>
        </div>

        {/* Search known persons */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Buscar persona conocida..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary"
          />
        </div>

        {/* Known persons list */}
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : knownPersons.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-4">
              No hay personas conocidas registradas
            </p>
          ) : (
            knownPersons.map((kp) => {
              const kpPhoto = kp.photo_url
                ? `${process.env.NEXT_PUBLIC_API_URL}/api/snapshots/${kp.photo_url}`
                : null;
              const isSelected = selectedTarget?.id === kp.id;
              return (
                <button
                  key={kp.id}
                  onClick={() => setSelectedTarget(isSelected ? null : kp)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left ${
                    isSelected
                      ? "bg-blue-500/10 border-blue-500/40"
                      : "bg-background border-border hover:border-border-hover"
                  }`}
                >
                  <div className="w-10 h-10 rounded-full bg-surface flex items-center justify-center overflow-hidden flex-shrink-0">
                    {kpPhoto ? (
                      <img src={kpPhoto} alt={kp.name} className="w-full h-full object-cover" />
                    ) : (
                      <User className="w-5 h-5 text-text-muted" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {kp.name}
                    </p>
                    <p className="text-xs text-text-muted">
                      {[kp.department, kp.employee_id].filter(Boolean).join(" - ") || "Sin detalles"}
                    </p>
                  </div>
                  {isSelected && (
                    <Check className="w-5 h-5 text-blue-400 flex-shrink-0" />
                  )}
                </button>
              );
            })
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={handleMerge}
            disabled={submitting || !selectedTarget}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {submitting ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Link className="w-4 h-4" />
            )}
            Fusionar
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

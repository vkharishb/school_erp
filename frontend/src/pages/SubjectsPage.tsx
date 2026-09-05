import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { academicApi, foundationApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { hasPermission } from "../utils/permissions";
import { apiErrorMessage } from "../utils/apiError";
import type { Campus, Subject } from "../types";

export default function SubjectsPage() {
  const { schoolId = "" } = useParams();
  const user = useAuthStore((s) => s.user);
  const canManage = hasPermission(user, "subject.manage");
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [campusId, setCampusId] = useState("");
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ code: "", name: "" });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ code: "", name: "" });

  const loadCampuses = async () => {
    try {
      const items = await foundationApi.campuses(schoolId);
      setCampuses(items);
      setCampusId((current) => current || user?.campus_id || items[0]?.id || "");
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to load campuses"));
    }
  };

  useEffect(() => {
    if (schoolId) void loadCampuses();
  }, [schoolId, user?.campus_id]);

  const load = async () => {
    if (!campusId) return;
    try {
      setSubjects(await academicApi.subjects(campusId));
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to load subjects"));
    }
  };

  useEffect(() => {
    setEditingId(null);
    void load();
  }, [campusId]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      await academicApi.createSubject(campusId, { code: form.code.trim(), name: form.name.trim() });
      setForm({ code: "", name: "" });
      setMessage("Subject created.");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to create subject"));
    }
  };

  const startEdit = (subject: Subject) => {
    setError("");
    setMessage("");
    setEditingId(subject.id);
    setEditForm({ code: subject.code, name: subject.name });
  };

  const saveEdit = async (subjectId: string) => {
    setError("");
    setMessage("");
    try {
      await academicApi.updateSubject(subjectId, {
        code: editForm.code.trim(),
        name: editForm.name.trim(),
      });
      setEditingId(null);
      setMessage("Subject updated and audit logged.");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to update subject"));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Subjects</h1>
        <p className="mt-1 text-gray-500">Maintain the subject master for each campus.</p>
      </div>
      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      <section className="card">
        <label>
          <span className="label">Campus / Branch</span>
          <select className="input max-w-md" value={campusId} onChange={(e) => setCampusId(e.target.value)}>
            <option value="">Select campus</option>
            {campuses.map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}
          </select>
        </label>
      </section>

      {canManage && campusId && (
        <form onSubmit={create} className="card grid grid-cols-1 gap-4 md:grid-cols-3">
          <label><span className="label">Subject Code</span><input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></label>
          <label><span className="label">Subject Name</span><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
          <div className="flex items-end"><button className="btn-primary">Create Subject</button></div>
        </form>
      )}

      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left"><th className="py-2">Code</th><th>Name</th><th>Status</th>{canManage && <th className="text-right">Actions</th>}</tr></thead>
          <tbody>
            {subjects.map((subject) => {
              const editing = editingId === subject.id;
              return (
                <tr key={subject.id} className="border-b last:border-0">
                  <td className="py-3">{editing ? <input className="input min-w-32" value={editForm.code} onChange={(e) => setEditForm({ ...editForm, code: e.target.value })} /> : <span className="font-mono text-xs">{subject.code}</span>}</td>
                  <td>{editing ? <input className="input min-w-48" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /> : subject.name}</td>
                  <td>{subject.is_active ? "Active" : "Inactive"}</td>
                  {canManage && (
                    <td className="text-right">
                      {editing ? (
                        <div className="flex justify-end gap-2">
                          <button type="button" className="btn-primary" onClick={() => void saveEdit(subject.id)} disabled={!editForm.code.trim() || !editForm.name.trim()}>Save</button>
                          <button type="button" className="btn-secondary" onClick={() => setEditingId(null)}>Cancel</button>
                        </div>
                      ) : (
                        <button type="button" className="btn-secondary" onClick={() => startEdit(subject)}>Edit</button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {subjects.length === 0 && <div className="py-8 text-center text-gray-500">No subjects configured.</div>}
      </section>
    </div>
  );
}

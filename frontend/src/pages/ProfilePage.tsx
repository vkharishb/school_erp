import { useState } from "react";
import { Link } from "react-router-dom";
import { Mail, Phone, ShieldCheck, UserRound } from "lucide-react";
import { authApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";
import { displayDesignation } from "../utils/account";
import {
  EMAIL_ERROR,
  MOBILE_ERROR,
  isValidEmail,
  isValidIndianMobile,
  normalizeIndianMobile,
} from "../utils/contactValidation";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  const initialPhone = (() => {
    const phone = user?.phone || "";

    if (/^\+91\d{10}$/.test(phone)) {
      return phone.slice(3);
    }

    return phone.replace(/\D/g, "").slice(-10);
  })();

  const [form, setForm] = useState({
    full_name: user?.full_name || "",
    designation: user?.designation || "Platform Owner",
    email: user?.email || "",
    phone: initialPhone,
  });

  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const save = async () => {
    setError("");
    setMessage("");

    if (!isValidEmail(form.email)) {
      setError(EMAIL_ERROR);
      return;
    }

    if (!isValidIndianMobile(form.phone)) {
      setError(MOBILE_ERROR);
      return;
    }

    setBusy(true);

    try {
      await authApi.updateProfile({
        ...form,
        email: form.email.trim(),
        phone: normalizeIndianMobile(form.phone),
      });

      await fetchMe();
      setEditing(false);
      setMessage("Profile updated successfully.");
    } catch (e) {
      setError(apiErrorMessage(e, "Unable to update profile."));
    } finally {
      setBusy(false);
    }
  };

  const handlePhoneChange = (value: string) => {
    const digitsOnly = value.replace(/\D/g, "").slice(0, 10);

    setForm({
      ...form,
      phone: digitsOnly,
    });
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
        <p className="mt-1 text-gray-500">
          Your identity and contact information.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {message && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <section className="card text-center">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-primary-100 text-primary-800">
            <UserRound size={46} />
          </div>

          <h2 className="mt-4 text-xl font-bold">{user?.full_name}</h2>
          <p className="text-sm text-gray-500">
            {displayDesignation(user)}
          </p>

          <span className="mt-3 inline-flex rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
            Active
          </span>

          <div className="mt-6 space-y-3 border-t pt-5 text-left text-sm">
            <p className="flex gap-2">
              <Mail size={17} />
              {user?.email || "No email configured"}
            </p>

            <p className="flex gap-2">
              <Phone size={17} />
              {user?.phone || "No phone configured"}
            </p>

            <p className="text-xs text-gray-500">
              Username:{" "}
              <span className="font-mono">{user?.username}</span>
            </p>
          </div>
        </section>

        <section className="card">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Profile details</h2>
              <p className="text-sm text-gray-500">
                Update your contact profile.
              </p>
            </div>

            {!editing && (
              <button
                className="btn-secondary"
                onClick={() => setEditing(true)}
              >
                Edit Profile
              </button>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <span className="label">
                Full Name<span className="text-red-600">*</span>
              </span>
              <input
                className="input"
                disabled={!editing}
                value={form.full_name}
                onChange={(e) =>
                  setForm({ ...form, full_name: e.target.value })
                }
              />
            </label>

            <label>
              <span className="label">Designation</span>
              <input
                className="input"
                disabled
                value={form.designation}
              />
            </label>

            <label>
              <span className="label">
                Email<span className="text-red-600">*</span>
              </span>
              <input
                className="input"
                type="email"
                disabled={!editing}
                value={form.email}
                onChange={(e) =>
                  setForm({ ...form, email: e.target.value })
                }
              />
            </label>

            <label>
              <span className="label">
                Phone<span className="text-red-600">*</span>
              </span>
              <input
                className="input"
                type="text"
                inputMode="numeric"
                maxLength={10}
                disabled={!editing}
                value={form.phone}
                onChange={(e) => handlePhoneChange(e.target.value)}
              />
            </label>
          </div>

          {editing && (
            <div className="mt-5 flex gap-3">
              <button
                className="btn-primary"
                disabled={busy || form.full_name.trim().length < 2}
                onClick={() => void save()}
              >
                {busy ? "Saving..." : "Save Changes"}
              </button>

              <button
                className="btn-secondary"
                disabled={busy}
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </div>
          )}

          <div className="mt-8 flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 p-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-primary-700" />
              <div>
                <p className="font-medium">Account Security</p>
                <p className="text-sm text-gray-500">
                  Change your password and protect the account.
                </p>
              </div>
            </div>

            <Link className="btn-secondary" to="/account-security">
              Open
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
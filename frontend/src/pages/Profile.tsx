import { useState } from "react";
import { api } from "../api";
import { googleStartHref, useAuth } from "../auth";
import type { User } from "../types";

export function Profile() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  if (!user) return null;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const next = await api<User>("/api/me", {
        method: "PATCH",
        body: JSON.stringify({
          display_name: name,
          current_password: currentPassword || null,
          new_password: newPassword || null,
        }),
      });
      setUser(next);
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Profile saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save");
    }
  }

  async function disconnect() {
    try {
      setUser(await api<User>("/api/auth/google/disconnect", { method: "POST" }));
      setMessage("Google disconnected.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not disconnect Google");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 520 }} onSubmit={(event) => void save(event)}>
      <h1>Profile</h1>
      <p className="muted">{user.email}</p>
      {error && <p className="danger">{error}</p>}
      {message && <p className="good">{message}</p>}
      <label className="field">Display name<input value={name} onChange={(event) => setName(event.target.value)} minLength={3} maxLength={24} required /></label>
      <label className="field">{user.has_password ? "Current password" : "No password yet"}
        {user.has_password && <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />}
      </label>
      <label className="field">{user.has_password ? "New password" : "Set a password"}
        <input type="password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
      </label>
      <button className="btn primary" type="submit">Save profile</button>
      <div className="row">
        {user.google_connected ? (
          <button className="btn" type="button" onClick={() => void disconnect()}>Disconnect Google</button>
        ) : (
          <a className="btn" href={googleStartHref(true)}>Connect Google</a>
        )}
        {user.role !== "user" && <a href="/api/docs">API reference</a>}
      </div>
    </form>
  );
}

import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { googleStartHref, useAuth } from "../auth";
import { DISCLAIMER } from "../format";
import type { User } from "../types";

export function Landing() {
  const { user } = useAuth();
  if (user && !user.display_name_set) return <Navigate to="/setup" replace />;
  if (user?.display_name_set) return <HomeRedirect />;
  return (
    <section className="stack" style={{ paddingTop: "2rem" }}>
      <p className="muted">Men's college football and basketball</p>
      <h1 style={{ fontSize: "clamp(3rem, 8vw, 5.5rem)", margin: 0 }}>Rank the week.</h1>
      <p style={{ maxWidth: "38rem", fontSize: "1.15rem" }}>
        Build your top 25, lock it in before the deadline, and see how close you were when the poll comes out.
      </p>
      <div className="row">
        <Link className="btn primary" to="/register">Create account</Link>
        <Link className="btn" to="/login">Log in</Link>
        <Link className="btn" to="/rules">How scoring works</Link>
      </div>
    </section>
  );
}

function HomeRedirect() {
  const navigate = useNavigate();
  useEffect(() => { navigate("/home", { replace: true }); }, [navigate]);
  return null;
}

export function Login() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(params.get("error") === "google" ? "Google sign-in is unavailable right now." : "");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const user = await api<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setUser(user);
      navigate(user.display_name_set ? "/home" : "/setup");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not log in");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 460 }} onSubmit={(event) => void submit(event)}>
      <h1>Log in</h1>
      {error && <p className="danger">{error}</p>}
      <label className="field">Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label className="field">Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      <button className="btn primary" type="submit">Log in</button>
      <a className="btn" href={googleStartHref()}>Continue with Google</a>
      <div className="row auth-links">
        <Link to="/register">Create an account</Link>
        <Link to="/reset">Forgot password</Link>
      </div>
      <p className="muted">{DISCLAIMER}</p>
    </form>
  );
}

export function Register() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const user = await api<User>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, display_name: displayName || null }),
      });
      setUser(user);
      navigate("/setup");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the account");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 480 }} onSubmit={(event) => void submit(event)}>
      <h1>Create account</h1>
      <p>You'll confirm a public display name before you can play. We won't use your real name.</p>
      {error && <p className="danger">{error}</p>}
      <label className="field">Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label className="field">Password<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      <label className="field">Display name, optional<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={24} /></label>
      <p className="muted">{DISCLAIMER}</p>
      <button className="btn primary" type="submit">Create account</button>
      <a className="btn" href={googleStartHref()}>Continue with Google</a>
      <Link to="/login">Already have an account? Log in</Link>
    </form>
  );
}

export function Magic() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const token = params.get("token");

  useEffect(() => {
    if (!token) return;
    api<User>("/api/auth/magic-link/consume", { method: "POST", body: JSON.stringify({ token }) })
      .then((user) => {
        setUser(user);
        navigate(user.display_name_set ? "/home" : "/setup");
      })
      .catch((reason: Error) => setError(reason.message));
  }, [token, navigate, setUser]);

  async function requestLink(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/auth/magic-link", { method: "POST", body: JSON.stringify({ email }) });
      setMessage("Check your email for a sign-in link.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not send the link");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 460 }} onSubmit={(event) => void requestLink(event)}>
      <h1>Email sign-in</h1>
      {error && <p className="danger">{error}</p>}
      {message && <p className="good">{message}</p>}
      <label className="field">Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <button className="btn primary" type="submit">Send a link</button>
    </form>
  );
}

export function Reset() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const token = params.get("token");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (token) {
        const user = await api<User>("/api/auth/password/reset", { method: "POST", body: JSON.stringify({ token, password }) });
        setUser(user);
        navigate(user.display_name_set ? "/home" : "/setup");
      } else {
        await api("/api/auth/password/forgot", { method: "POST", body: JSON.stringify({ email }) });
        setMessage("If that email has an account, a reset link is on the way.");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not reset the password");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 460 }} onSubmit={(event) => void submit(event)}>
      <h1>{token ? "Choose a new password" : "Reset password"}</h1>
      {error && <p className="danger">{error}</p>}
      {message && <p className="good">{message}</p>}
      {token ? (
        <label className="field">New password<input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      ) : (
        <label className="field">Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      )}
      <button className="btn primary" type="submit">{token ? "Save password" : "Send reset link"}</button>
    </form>
  );
}

export function Setup() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.display_name ?? "");
  const [error, setError] = useState("");
  useEffect(() => { if (user) setName(user.display_name); }, [user]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const next = await api<User>("/api/me/display-name", { method: "POST", body: JSON.stringify({ display_name: name }) });
      setUser(next);
      navigate("/home");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the name");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 480 }} onSubmit={(event) => void submit(event)}>
      <h1>Choose a public name</h1>
      <p>This is the only name other players see. A suggestion is filled in. Change it, or keep it, then confirm.</p>
      {error && <p className="danger">{error}</p>}
      <label className="field">Display name<input value={name} onChange={(event) => setName(event.target.value)} minLength={3} maxLength={24} required /></label>
      <button className="btn primary" type="submit">Confirm name</button>
    </form>
  );
}

export function Rules() {
  return (
    <article className="stack">
      <h1>Proximity Points</h1>
      <p>A week score is proximity points plus a small bubble bonus. Points are never negative. A bad week adds little or nothing. It does not subtract points you already earned. Your season score is the sum of that season's weeks. A perfect top 25 is 250 proximity points. Bubble points add at most 9 more.</p>
      <div className="panel">
        <h2>Top 25</h2>
        <p>For each official team, distance is how far your rank is from the official rank.</p>
        <p>Tied teams share one official rank. Both show that rank with a T, and the next team takes the next open number. Your ballot still uses each number once, so only one of those teams can be an exact match.</p>
        <table className="table">
          <thead><tr><th>Distance</th><th>Points</th></tr></thead>
          <tbody>
            {[
              ["Exact", "10"],
              ["Off by 1", "8"],
              ["Off by 2", "6"],
              ["Off by 3", "4"],
              ["Off by 4", "2"],
              ["Off by 5, 6, or 7", "1"],
              ["Off by 8 or more, or missing", "0"],
            ].map(([distance, points]) => <tr key={distance}><td>{distance}</td><td>{points}</td></tr>)}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <h2>Also receiving</h2>
        <p>If you ranked a team that missed the top 25 and is on the also-receiving list:</p>
        <table className="table">
          <thead><tr><th>Your rank</th><th>Bubble points</th></tr></thead>
          <tbody>
            <tr><td>23, 24, or 25</td><td>2</td></tr>
            <tr><td>20, 21, or 22</td><td>1</td></tr>
            <tr><td>1 through 19</td><td>0</td></tr>
          </tbody>
        </table>
        <p>A team left off that list scores 0. Filling ranks 20 through 25 with teams on that list is 9 points.</p>
      </div>
      <div className="panel stack">
        <h2>Example</h2>
        <p>This five-team board only shows the proximity math. A real week has 25 teams and maxes at 250 proximity points.</p>
        <table className="table">
          <thead><tr><th>Official</th><th>Your rank</th><th>Points</th></tr></thead>
          <tbody>
            <tr><td>1 Duke</td><td>1</td><td>10</td></tr>
            <tr><td>2 Kansas</td><td>3</td><td>8</td></tr>
            <tr><td>3 Houston</td><td>2</td><td>8</td></tr>
            <tr><td>4 Purdue</td><td>Missing</td><td>0</td></tr>
            <tr><td>5 UConn</td><td>4</td><td>8</td></tr>
          </tbody>
        </table>
        <p>Proximity subtotal: 34 of 50.</p>
        <p>On a real ballot, Arizona missed the top 25 and was on the also-receiving list, and you ranked Arizona 25: 2 bubble points. Yale was also on that list, but you ranked Yale 8: 0 bubble points.</p>
      </div>
      <div className="panel">
        <h2>Tiebreakers</h2>
        <p>Ranks are unique. If the season total is tied, these steps decide the order:</p>
        <ol>
          <li>Higher score in the most recent published week</li>
          <li>More exact hits in the season</li>
          <li>Lower total distance among official top-25 teams you actually ranked. An empty overlap sorts behind any measured distance. Bubble picks are left out of this step.</li>
          <li>Earlier first submitted ballot of the season</li>
          <li>Lower account id, so two players cannot share a place</li>
        </ol>
        <p>When one of these steps separates two players, the standings say which one.</p>
      </div>
    </article>
  );
}

export function Disclaimer() {
  return (
    <article className="panel stack">
      <h1>Independence</h1>
      <p>{DISCLAIMER}</p>
      <p>Rankings in this game are entered by the people who run it. They are a fan record of a public poll, not an official release.</p>
    </article>
  );
}

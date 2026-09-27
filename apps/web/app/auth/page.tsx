"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/authContext";

export default function AuthPage() {
  const router = useRouter();
  const { user, login, logout } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setNotice("Please enter your email address.");
      return;
    }
    login(email, name || "Shopping Explorer");
    setNotice("Logged in successfully! Redirecting...");
    setTimeout(() => {
      router.push("/");
    }, 800);
  };

  const handleDemoLogin = (demoEmail: string, demoName: string) => {
    login(demoEmail, demoName);
    setNotice(`Signed in as ${demoName}! Redirecting...`);
    setTimeout(() => {
      router.push("/");
    }, 600);
  };

  return (
    <div className="mx-auto max-w-md py-12 space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white shadow-lg shadow-brand-500/30">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h1 className="text-2xl font-black text-slate-900">
          {user.isAuthenticated ? "Account Management" : isSignUp ? "Create PricePilot Account" : "Sign in to PricePilot"}
        </h1>
        <p className="text-xs text-slate-500">
          Access universal price forecasting, automatic price-drop refunds, and multi-retailer tracking
        </p>
      </div>

      {notice && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-3.5 text-center text-xs font-bold text-emerald-800">
          {notice}
        </div>
      )}

      {user.isAuthenticated ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm text-center space-y-4">
          <img
            src={user.avatar}
            alt={user.name}
            className="mx-auto h-20 w-20 rounded-2xl object-cover ring-2 ring-slate-100 shadow-md"
          />
          <div>
            <h2 className="text-base font-bold text-slate-900">{user.name}</h2>
            <p className="text-xs text-slate-500">{user.email}</p>
            <span className="mt-2 inline-block rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-bold text-emerald-700">
              {user.membershipTier}
            </span>
          </div>

          <div className="pt-2 flex flex-col gap-2">
            <button
              type="button"
              onClick={() => router.push("/profile")}
              className="w-full rounded-xl bg-slate-900 py-2.5 text-xs font-bold text-white hover:bg-brand-600 transition"
            >
              Go to Profile & Addresses →
            </button>
            <button
              type="button"
              onClick={() => {
                logout();
                setNotice("Signed out of your account.");
              }}
              className="w-full rounded-xl border border-rose-200 bg-rose-50 py-2.5 text-xs font-bold text-rose-700 hover:bg-rose-100 transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
          {/* Quick 1-Click Demo Profiles */}
          <div className="rounded-2xl bg-indigo-50/70 p-3.5 border border-indigo-100 space-y-2">
            <div className="text-[11px] font-bold text-indigo-900 uppercase tracking-wider">
              ⚡ 1-Click Instant Sign In
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleDemoLogin("rahul.sharma@example.com", "Rahul Sharma")}
                className="flex-1 rounded-xl bg-white border border-indigo-200 p-2 text-left hover:border-brand-500 shadow-xs transition"
              >
                <div className="text-xs font-bold text-slate-900">Rahul Sharma</div>
                <div className="text-[10px] text-slate-500">Pro Member (Active)</div>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin("priya.patel@example.com", "Priya Patel")}
                className="flex-1 rounded-xl bg-white border border-indigo-200 p-2 text-left hover:border-brand-500 shadow-xs transition"
              >
                <div className="text-xs font-bold text-slate-900">Priya Patel</div>
                <div className="text-[10px] text-slate-500">Deal Hunter</div>
              </button>
            </div>
          </div>

          <div className="relative text-center text-xs text-slate-400">
            <span className="bg-white px-3 relative z-10">or continue with email</span>
            <div className="absolute inset-y-1/2 inset-x-0 border-t border-slate-200 -z-0" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {isSignUp && (
              <div>
                <label className="block font-bold text-slate-700 mb-1">Your Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. John Doe"
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}

            <div>
              <label className="block font-bold text-slate-700 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                className="w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-bold text-slate-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              className="w-full rounded-xl bg-slate-900 py-3 text-xs font-bold text-white hover:bg-brand-600 transition shadow-sm"
            >
              {isSignUp ? "Create My Account" : "Sign In to ShoppingOS"}
            </button>
          </form>

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-xs font-semibold text-brand-600 hover:underline"
            >
              {isSignUp ? "Already have an account? Sign In" : "Don't have an account? Sign Up Free"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

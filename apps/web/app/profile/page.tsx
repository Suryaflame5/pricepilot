"use client";

import { useState } from "react";
import { useAuth } from "@/lib/authContext";
import { inr } from "@/lib/formatting";

export default function ProfilePage() {
  const { user, updateProfile, logout } = useAuth();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user.name);
  const [phone, setPhone] = useState(user.phone);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile({ name, phone });
    setEditing(false);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Profile Header Card */}
      <div className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="relative">
            <img
              src={user.avatar}
              alt={user.name}
              className="h-24 w-24 rounded-2xl object-cover ring-4 ring-slate-100 shadow-md"
            />
            <span className="absolute -bottom-2 -right-2 rounded-full bg-emerald-500 px-2 py-0.5 text-[10px] font-black text-white shadow-sm">
              PRO
            </span>
          </div>

          <div className="flex-1 text-center sm:text-left space-y-1">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <h1 className="text-2xl font-black text-slate-900">{user.name}</h1>
              <span className="inline-block rounded-full bg-indigo-50 px-3 py-0.5 text-xs font-bold text-indigo-700 border border-indigo-200">
                {user.membershipTier}
              </span>
            </div>
            <p className="text-xs text-slate-500">{user.email} • {user.phone}</p>
            <p className="text-xs text-emerald-600 font-semibold pt-1">
              ✓ 7-Day Automatic Price Drop Guarantee Active on All Purchases
            </p>
          </div>

          <button
            type="button"
            onClick={() => setEditing(!editing)}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition shadow-sm"
          >
            {editing ? "Cancel" : "Edit Profile"}
          </button>
        </div>

        {savedSuccess && (
          <div className="mt-4 rounded-xl bg-emerald-50 p-3 text-xs font-bold text-emerald-700 border border-emerald-200">
            ✓ Profile updated successfully!
          </div>
        )}

        {/* Edit Form */}
        {editing && (
          <form onSubmit={handleSave} className="mt-6 border-t border-slate-100 pt-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs focus:border-brand-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Phone Number</label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs focus:border-brand-500 focus:outline-none"
              />
            </div>
            <div className="sm:col-span-2 flex justify-end">
              <button
                type="submit"
                className="rounded-xl bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-brand-600 transition"
              >
                Save Changes
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Savings & Intelligence Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <div className="text-2xl font-black text-emerald-600">{inr(user.totalSaved)}</div>
          <div className="text-xs text-slate-500 mt-1 font-medium">Total Arbitrage Saved</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <div className="text-2xl font-black text-slate-900">{user.activeOrdersCount}</div>
          <div className="text-xs text-slate-500 mt-1 font-medium">Active Shipments</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <div className="text-2xl font-black text-slate-900">{user.priceAlertsCount}</div>
          <div className="text-xs text-slate-500 mt-1 font-medium">Active Price Alerts</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-center">
          <div className="text-2xl font-black text-indigo-600">VIP Pro</div>
          <div className="text-xs text-slate-500 mt-1 font-medium">Protection Status</div>
        </div>
      </div>

      {/* Saved Delivery Addresses */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Saved Delivery Addresses</h2>
            <p className="text-xs text-slate-500">Auto-filled at checkout for Flipkart, Amazon, and Meesho orders</p>
          </div>
          <button
            type="button"
            className="text-xs font-bold text-brand-600 hover:underline"
          >
            + Add New Address
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {user.addresses.map((addr) => (
            <div
              key={addr.id}
              className={`rounded-2xl p-4 border transition ${
                addr.isDefault
                  ? "border-brand-500 bg-brand-50/20 ring-1 ring-brand-500/20"
                  : "border-slate-200 bg-slate-50/50"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-xs text-slate-900">{addr.label}</span>
                {addr.isDefault && (
                  <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-700">
                    Default
                  </span>
                )}
              </div>
              <div className="text-xs font-semibold text-slate-800">{addr.name}</div>
              <div className="text-xs text-slate-500 mt-1 leading-relaxed">
                {addr.street}, {addr.city}, {addr.state} - {addr.pincode}
              </div>
              <div className="text-[11px] text-slate-400 mt-2">Phone: {addr.phone}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3">
          Price Alert Notification Channels
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
            <div>
              <div className="font-bold text-slate-800">WhatsApp Instant Alerts</div>
              <div className="text-slate-400 text-[11px]">Instant message when price hits target</div>
            </div>
            <span className="font-bold text-emerald-600">Enabled</span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
            <div>
              <div className="font-bold text-slate-800">Email Price Reports</div>
              <div className="text-slate-400 text-[11px]">Weekly price drop digest</div>
            </div>
            <span className="font-bold text-emerald-600">Enabled</span>
          </div>
        </div>
      </div>
    </div>
  );
}

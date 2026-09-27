"use client";

import { useEffect, useState } from "react";
import { RETAILER_METADATA } from "@/lib/retailers";

export default function SettingsPage() {
  const [urgency, setUrgency] = useState("normal");
  const [maxWait, setMaxWait] = useState("30");
  const [currency, setCurrency] = useState("INR");
  const [forecastHorizon, setForecastHorizon] = useState("720"); // 30 days
  const [alertThreshold, setAlertThreshold] = useState("5");
  const [enabledRetailers, setEnabledRetailers] = useState<Record<string, boolean>>({
    flipkart: true,
    amazon: true,
    meesho: true,
    myntra: true,
    nykaa: true,
    croma: true,
    "reliance-digital": true,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const u = localStorage.getItem("urgency");
      if (u) setUrgency(u);
      const m = localStorage.getItem("maxWait");
      if (m) setMaxWait(m);
      const r = localStorage.getItem("enabled_retailers");
      if (r) setEnabledRetailers(JSON.parse(r));
    } catch {
      // fallback
    }
  }, []);

  const toggleRetailer = (id: string) => {
    setEnabledRetailers((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleSave = () => {
    localStorage.setItem("urgency", urgency);
    localStorage.setItem("maxWait", maxWait);
    localStorage.setItem("currency", currency);
    localStorage.setItem("forecast_horizon", forecastHorizon);
    localStorage.setItem("enabled_retailers", JSON.stringify(enabledRetailers));
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const retailers = Object.values(RETAILER_METADATA);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-black text-slate-900">ShoppingOS Settings & Preferences</h1>
        <p className="text-xs text-slate-500">
          Customize price forecasting horizons, retailer exclusions, alert thresholds, and currency
        </p>
      </div>

      {saved && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-xs font-bold text-emerald-800 flex items-center gap-2">
          <span>✓</span>
          <span>Preferences updated and saved to your browser!</span>
        </div>
      )}

      {/* 1. Retailers Inclusion Hub */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-base font-bold text-slate-900">Tracked E-Commerce Retailers</h2>
          <p className="text-xs text-slate-500">
            Select which platforms the real-time scraper should search and include in price comparisons
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {retailers.map((r) => {
            const isEnabled = enabledRetailers[r.id] ?? true;
            return (
              <label
                key={r.id}
                className={`flex items-center justify-between p-3.5 rounded-2xl border cursor-pointer transition ${
                  isEnabled
                    ? "border-slate-300 bg-white shadow-xs"
                    : "border-slate-100 bg-slate-50 opacity-60"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`h-8 w-8 flex items-center justify-center rounded-xl font-bold text-xs ${r.badgeColor}`}>
                    {r.logoShort}
                  </span>
                  <div>
                    <div className="font-bold text-xs text-slate-900">{r.displayName}</div>
                    <div className="text-[11px] text-slate-400">{r.deliveryEstimate}</div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={isEnabled}
                  onChange={() => toggleRetailer(r.id)}
                  className="h-4 w-4 rounded text-brand-600 focus:ring-brand-500"
                />
              </label>
            );
          })}
        </div>
      </div>

      {/* 2. Purchase Timing & Decision Parameters */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-base font-bold text-slate-900">Purchase Timing & Price Sensitivity Parameters</h2>
          <p className="text-xs text-slate-500">
            Governs the mathematical optimization between Expected Utility of Waiting vs Buying Now
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 mb-1">Shopping Urgency</label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value)}
              className="w-full rounded-xl border border-slate-300 p-2.5 focus:border-brand-500 focus:outline-none"
            >
              <option value="normal">Normal — Patient (recommends waiting for expected dips)</option>
              <option value="high">High — Urgent (prioritizes immediate purchase / low wait penalty)</option>
            </select>
          </div>

          <div>
            <label className="block font-bold text-slate-700 mb-1">Default Forecast Horizon</label>
            <select
              value={forecastHorizon}
              onChange={(e) => setForecastHorizon(e.target.value)}
              className="w-full rounded-xl border border-slate-300 p-2.5 focus:border-brand-500 focus:outline-none"
            >
              <option value="168">7 Days (Short-term flash sale drops)</option>
              <option value="720">30 Days (Medium-term monthly sales)</option>
              <option value="2160">90 Days (Quarterly festive discount cycles)</option>
            </select>
          </div>

          <div>
            <label className="block font-bold text-slate-700 mb-1">Maximum Wait Period (Days)</label>
            <input
              type="number"
              value={maxWait}
              onChange={(e) => setMaxWait(e.target.value)}
              className="w-full rounded-xl border border-slate-300 p-2.5 focus:border-brand-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block font-bold text-slate-700 mb-1">Price Drop Notification Threshold</label>
            <select
              value={alertThreshold}
              onChange={(e) => setAlertThreshold(e.target.value)}
              className="w-full rounded-xl border border-slate-300 p-2.5 focus:border-brand-500 focus:outline-none"
            >
              <option value="2">2% or greater price dip</option>
              <option value="5">5% or greater price dip (Recommended)</option>
              <option value="10">10% or greater major sale dip</option>
              <option value="15">15%+ massive discount alert</option>
            </select>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={handleSave}
          className="rounded-xl bg-slate-900 px-6 py-3 text-xs font-bold text-white hover:bg-brand-600 transition shadow-md"
        >
          Save All Preferences
        </button>
      </div>
    </div>
  );
}

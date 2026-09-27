"use client";

import { RETAILER_METADATA } from "@/lib/retailers";

export default function Footer() {
  const retailers = Object.values(RETAILER_METADATA);

  return (
    <footer className="mt-20 border-t border-slate-200/80 bg-white text-slate-600">
      {/* Retailers Supported Bar */}
      <div className="border-b border-slate-100 bg-slate-50/60 py-6">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-indigo-700">
                Multi-Platform Price Intelligence
              </p>
              <p className="text-sm text-slate-700 font-medium">
                Live price tracking, store comparisons, and deal discovery across India&apos;s leading online retailers
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {retailers.map((r) => (
                <span
                  key={r.id}
                  className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1 text-xs font-semibold border border-slate-200 bg-white text-slate-700 shadow-2xs"
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  {r.displayName}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white font-black text-sm shadow-sm shadow-indigo-500/20">
                P
              </div>
              <span className="text-base font-black text-slate-900">PricePilot</span>
            </div>
            <p className="mt-3 text-xs text-slate-500 leading-relaxed font-medium">
              Real-time multi-retailer shopping assistant and price comparison engine. Continuous store tracking, price forecasting, and automated price drop detection.
            </p>
            <div className="mt-4 flex items-center gap-2 text-xs font-bold text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              All Retailer Services Online & Active
            </div>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">Shopping Tools</h4>
            <ul className="mt-3 space-y-2 text-xs text-slate-500 font-medium">
              <li><a href="/search" className="hover:text-indigo-600 transition">Universal Product Search</a></li>
              <li><a href="/cart" className="hover:text-indigo-600 transition">Shopping Cart & Best Store</a></li>
              <li><a href="/orders" className="hover:text-indigo-600 transition">Orders & Price Protection</a></li>
              <li><a href="/watchlist" className="hover:text-indigo-600 transition">Price Drop Watchlist</a></li>
              <li><a href="/alerts" className="hover:text-indigo-600 transition">Target Price Alerts</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">Price Intelligence</h4>
            <ul className="mt-3 space-y-2 text-xs text-slate-500 font-medium">
              <li><a href="/intelligence" className="hover:text-purple-600 transition">Model Metrics & Evaluation</a></li>
              <li><a href="http://localhost:8000/docs" target="_blank" className="hover:text-purple-600 transition">FastAPI Interactive Docs ↗</a></li>
              <li><a href="/settings" className="hover:text-purple-600 transition">Notification & Store Preferences</a></li>
              <li><span className="text-slate-400">Multi-Horizon Price Forecasting</span></li>
              <li><span className="text-slate-400">Conformal Prediction Bounds</span></li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">User Account</h4>
            <ul className="mt-3 space-y-2 text-xs text-slate-500 font-medium">
              <li><a href="/profile" className="hover:text-indigo-600 transition">My Profile & Addresses</a></li>
              <li><a href="/orders" className="hover:text-indigo-600 transition">Track Packages & History</a></li>
              <li><a href="/settings" className="hover:text-indigo-600 transition">Retailer Preferences</a></li>
              <li><a href="/auth" className="hover:text-indigo-600 transition">Switch Account / Sign In</a></li>
            </ul>
          </div>
        </div>

        <div className="mt-8 border-t border-slate-100 pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 font-medium">
          <p>© 2026 PricePilot. Real-Time Multi-Retailer Price Comparison.</p>
          <p className="mt-2 sm:mt-0 text-slate-400 font-mono">Universal Scraper Active • Production Build</p>
        </div>
      </div>
    </footer>
  );
}

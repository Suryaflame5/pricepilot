"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cartContext";
import { useAuth } from "@/lib/authContext";
import { useOrders } from "@/lib/orderContext";
import { inrCompact } from "@/lib/formatting";

export default function Navbar() {
  const router = useRouter();
  const { itemCount, subtotal } = useCart();
  const { user } = useAuth();
  const { orders } = useOrders();
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const activeOrders = orders.filter((o) => o.status !== "delivered").length;

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-xl shadow-xs">
      {/* Top Multi-Color Retailer Ticker */}
      <div className="bg-slate-950 px-4 py-1.5 text-center text-xs text-slate-300">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <span className="hidden sm:inline font-semibold text-slate-400">
            Multi-Store Live Price Scanner:
          </span>
          <div className="flex items-center gap-2.5 overflow-x-auto mx-auto sm:mx-0 py-0.5 text-[11px] font-semibold">
            <span className="rounded-md bg-amber-500/20 px-2 py-0.5 text-amber-300 border border-amber-500/30">
              Amazon
            </span>
            <span className="rounded-md bg-blue-500/20 px-2 py-0.5 text-blue-300 border border-blue-500/30">
              Flipkart
            </span>
            <span className="rounded-md bg-pink-500/20 px-2 py-0.5 text-pink-300 border border-pink-500/30">
              Meesho
            </span>
            <span className="rounded-md bg-rose-500/20 px-2 py-0.5 text-rose-300 border border-rose-500/30">
              Myntra
            </span>
            <span className="rounded-md bg-fuchsia-500/20 px-2 py-0.5 text-fuchsia-300 border border-fuchsia-500/30">
              Nykaa
            </span>
            <span className="rounded-md bg-teal-500/20 px-2 py-0.5 text-teal-300 border border-teal-500/30">
              Croma
            </span>
            <span className="rounded-md bg-red-500/20 px-2 py-0.5 text-red-300 border border-red-500/30">
              Reliance
            </span>
          </div>
          <span className="hidden md:inline font-medium text-emerald-400">
            ✓ 100% Free Price Comparison
          </span>
        </div>
      </div>

      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Brand Logo */}
        <div className="flex items-center gap-3">
          <a href="/" className="group flex items-center gap-2.5">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 text-white shadow-md shadow-indigo-500/25 transition duration-300 group-hover:scale-105 group-hover:shadow-indigo-500/40">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-black tracking-tight text-slate-900 group-hover:text-indigo-600 transition">
                  PricePilot
                </span>
                <span className="rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-2.5 py-0.5 text-[10px] font-black text-white uppercase tracking-wider shadow-2xs">
                  PRO
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-500">Universal Price Comparison & Deals</p>
            </div>
          </a>
        </div>

        {/* Global Live Search Bar */}
        <form onSubmit={handleSearchSubmit} className="hidden flex-1 max-w-md md:block">
          <div className="relative group">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search across Flipkart, Amazon, Meesho, Croma..."
              className="w-full rounded-2xl border border-slate-200 bg-slate-50/80 py-2.5 pl-10 pr-24 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-500/10 transition shadow-2xs"
            />
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400 group-focus-within:text-indigo-600 transition">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <button
              type="submit"
              className="absolute inset-y-1 right-1 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-3.5 text-xs font-bold text-white shadow-xs hover:from-indigo-700 hover:to-purple-700 transition"
            >
              Search
            </button>
          </div>
        </form>

        {/* Navigation Links with Distinct Colors */}
        <nav className="hidden lg:flex items-center gap-1.5 text-sm font-semibold">
          <a
            href="/search"
            className="rounded-xl px-3 py-1.5 text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 transition"
          >
            Explore Deals
          </a>
          <a
            href="/watchlist"
            className="rounded-xl px-3 py-1.5 text-slate-700 hover:bg-rose-50 hover:text-rose-600 transition"
          >
            Price Watch
          </a>
          <a
            href="/alerts"
            className="rounded-xl px-3 py-1.5 text-slate-700 hover:bg-amber-50 hover:text-amber-600 transition"
          >
            Alerts
          </a>
          <a
            href="/intelligence"
            className="rounded-xl px-3 py-1.5 text-slate-700 hover:bg-purple-50 hover:text-purple-600 transition flex items-center gap-1.5"
          >
            <span className="text-purple-600">🧠</span>
            <span>Price Intelligence</span>
          </a>
        </nav>

        {/* Action Group: Orders, Cart, Profile */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Orders Tracking Button */}
          <a
            href="/orders"
            className="relative flex items-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:border-indigo-300 hover:bg-indigo-50/50 hover:text-indigo-700 transition shadow-2xs"
            title="My Orders & Tracking"
          >
            <svg className="h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
            </svg>
            <span className="hidden sm:inline">Orders</span>
            {activeOrders > 0 && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-black text-white">
                {activeOrders}
              </span>
            )}
          </a>

          {/* Cart Button */}
          <a
            href="/cart"
            className="relative flex items-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 px-3.5 py-2 text-xs font-black text-white shadow-md shadow-emerald-600/20 hover:from-emerald-700 hover:to-teal-700 transition"
            title="Shopping Cart"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span>Cart</span>
            {itemCount > 0 ? (
              <span className="flex h-5 px-1.5 items-center justify-center rounded-full bg-white text-[11px] font-black text-emerald-700 shadow-2xs">
                {itemCount}
              </span>
            ) : null}
            {subtotal > 0 && (
              <span className="hidden md:inline border-l border-emerald-500/60 pl-2 text-white font-medium">
                {inrCompact(subtotal)}
              </span>
            )}
          </a>

          {/* Profile / Account Dropdown */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              type="button"
              className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-1.5 pr-2.5 text-xs font-semibold text-slate-700 hover:border-indigo-300 transition shadow-2xs"
            >
              <img
                src={user.avatar}
                alt={user.name}
                className="h-7 w-7 rounded-xl object-cover ring-2 ring-indigo-500/20"
              />
              <span className="hidden sm:inline font-bold text-slate-800">{user.name.split(" ")[0]}</span>
              <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 mt-2 w-60 rounded-3xl border border-slate-200 bg-white p-2.5 shadow-2xl ring-1 ring-black/5 z-50 animate-scale-in"
                onClick={() => setMenuOpen(false)}
              >
                <div className="border-b border-slate-100 px-3 py-2.5">
                  <div className="font-bold text-slate-900">{user.name}</div>
                  <div className="text-xs text-slate-500 truncate">{user.email}</div>
                  <span className="mt-1.5 inline-block rounded-full bg-gradient-to-r from-indigo-50 to-purple-50 px-2.5 py-0.5 text-[10px] font-black text-indigo-700 border border-indigo-200 uppercase tracking-wider">
                    {user.membershipTier}
                  </span>
                </div>
                <div className="py-1 text-xs text-slate-700 font-medium space-y-0.5">
                  <a href="/profile" className="flex items-center gap-2.5 rounded-xl px-3 py-2 hover:bg-indigo-50 hover:text-indigo-600 transition">
                    <span>👤</span> My Profile & Addresses
                  </a>
                  <a href="/orders" className="flex items-center gap-2.5 rounded-xl px-3 py-2 hover:bg-emerald-50 hover:text-emerald-700 transition">
                    <span>📦</span> Orders & Price Protection
                  </a>
                  <a href="/watchlist" className="flex items-center gap-2.5 rounded-xl px-3 py-2 hover:bg-rose-50 hover:text-rose-600 transition">
                    <span>♡</span> Saved Watchlist
                  </a>
                  <a href="/settings" className="flex items-center gap-2.5 rounded-xl px-3 py-2 hover:bg-slate-100 hover:text-slate-900 transition">
                    <span>⚙️</span> Settings & Retailers
                  </a>
                  <a href="/auth" className="flex items-center gap-2.5 rounded-xl px-3 py-2 hover:bg-amber-50 hover:text-amber-700 transition">
                    <span>🔐</span> Switch Account / Sign Out
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

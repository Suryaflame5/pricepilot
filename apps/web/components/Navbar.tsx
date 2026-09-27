"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cartContext";
import { useAuth } from "@/lib/authContext";
import { useOrders } from "@/lib/orderContext";
import { inrCompact } from "@/lib/formatting";

const NAV_CATEGORIES = [
  { name: "All Deals", href: "/search" },
  { name: "Smartphones", href: "/search?category=smartphones" },
  { name: "Laptops", href: "/search?category=laptops" },
  { name: "Audio", href: "/search?category=audio" },
  { name: "Fashion", href: "/search?category=fashion" },
  { name: "Appliances", href: "/search?category=appliances" },
  { name: "Beauty", href: "/search?category=beauty" },
];

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
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/90 bg-white/95 backdrop-blur-xl shadow-xs">
      {/* Top Professional Retailer Status Bar */}
      <div className="bg-slate-900 text-slate-300 px-4 py-1.5 text-xs border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold text-slate-200">Live Multi-Store Indexer Active:</span>
            <span className="hidden sm:inline">Flipkart • Amazon India • Meesho • Croma • Reliance Digital • Myntra • Nykaa</span>
          </div>
          <div className="flex items-center gap-3 text-[11px]">
            <span className="font-medium text-emerald-400 hidden md:inline">
              ✓ Direct Merchant Prices
            </span>
            <span className="text-slate-600 hidden md:inline">•</span>
            <span className="text-slate-300 font-semibold">
              Conformal AI Calibrated
            </span>
          </div>
        </div>
      </div>

      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Brand Logo: ShoppingOS */}
        <div className="flex items-center gap-3">
          <a href="/" className="group flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-white shadow-sm ring-1 ring-slate-800 transition duration-200 group-hover:bg-indigo-600">
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-lg font-black tracking-tight text-slate-950 group-hover:text-indigo-600 transition">
                  ShoppingOS
                </span>
                <span className="rounded-md bg-indigo-50 px-1.5 py-0.5 text-[9px] font-bold text-indigo-700 border border-indigo-200 uppercase tracking-wider">
                  AI TERMINAL
                </span>
              </div>
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                PricePilot Engine
              </p>
            </div>
          </a>
        </div>

        {/* Global Live Search Bar */}
        <form onSubmit={handleSearchSubmit} className="hidden flex-1 max-w-lg md:block">
          <div className="relative group">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search any product across Amazon, Flipkart, Meesho, Croma..."
              className="w-full rounded-xl border border-slate-300/80 bg-slate-50/70 py-2 pl-10 pr-24 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-600 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-600/10 transition font-medium"
            />
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 group-focus-within:text-indigo-600 transition">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <button
              type="submit"
              className="absolute inset-y-1 right-1 rounded-lg bg-slate-900 px-3 text-xs font-bold text-white hover:bg-indigo-600 transition"
            >
              Scan
            </button>
          </div>
        </form>

        {/* Navigation Links */}
        <nav className="hidden lg:flex items-center gap-1 text-xs font-semibold text-slate-700">
          <a
            href="/search"
            className="rounded-lg px-2.5 py-1.5 hover:bg-slate-100 hover:text-slate-900 transition"
          >
            Explore Deals
          </a>
          <a
            href="/watchlist"
            className="rounded-lg px-2.5 py-1.5 hover:bg-slate-100 hover:text-slate-900 transition"
          >
            Watchlist
          </a>
          <a
            href="/alerts"
            className="rounded-lg px-2.5 py-1.5 hover:bg-slate-100 hover:text-slate-900 transition"
          >
            Price Alerts
          </a>
          <a
            href="/intelligence"
            className="rounded-lg px-2.5 py-1.5 text-indigo-700 bg-indigo-50/80 border border-indigo-200/60 hover:bg-indigo-100/80 transition flex items-center gap-1"
          >
            <span>⚡</span>
            <span>Forecast AI</span>
          </a>
        </nav>

        {/* Action Group: Orders, Cart, Profile */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Orders Tracking Button */}
          <a
            href="/orders"
            className="relative flex items-center gap-1.5 rounded-xl border border-slate-200/90 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-slate-300 hover:bg-slate-50 transition shadow-2xs"
            title="My Orders & Tracking"
          >
            <svg className="h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
            </svg>
            <span className="hidden sm:inline">Orders</span>
            {activeOrders > 0 && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-black text-white">
                {activeOrders}
              </span>
            )}
          </a>

          {/* Cart Button */}
          <a
            href="/cart"
            className="relative flex items-center gap-2 rounded-xl bg-slate-950 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-indigo-600 transition shadow-xs"
            title="Shopping Cart"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span>Cart</span>
            {itemCount > 0 ? (
              <span className="flex h-4 px-1.5 items-center justify-center rounded-full bg-emerald-400 text-[10px] font-black text-slate-950">
                {itemCount}
              </span>
            ) : null}
            {subtotal > 0 && (
              <span className="hidden md:inline border-l border-slate-700 pl-2 text-slate-300 font-mono">
                {inrCompact(subtotal)}
              </span>
            )}
          </a>

          {/* Profile / Account Dropdown */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              type="button"
              className="flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white p-1 pr-2 text-xs font-semibold text-slate-700 hover:border-slate-300 transition shadow-2xs"
            >
              <img
                src={user.avatar}
                alt={user.name}
                className="h-6 w-6 rounded-lg object-cover ring-1 ring-slate-200"
              />
              <span className="hidden sm:inline font-bold text-slate-800">{user.name.split(" ")[0]}</span>
              <svg className="h-3 w-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 mt-2 w-56 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl ring-1 ring-black/5 z-50 animate-scale-in"
                onClick={() => setMenuOpen(false)}
              >
                <div className="border-b border-slate-100 px-3 py-2">
                  <div className="font-bold text-slate-900 text-xs">{user.name}</div>
                  <div className="text-[11px] text-slate-500 truncate">{user.email}</div>
                  <span className="mt-1 inline-block rounded-md bg-slate-100 px-2 py-0.5 text-[9px] font-bold text-slate-700 uppercase tracking-wider">
                    {user.membershipTier}
                  </span>
                </div>
                <div className="py-1 text-xs text-slate-700 font-medium space-y-0.5">
                  <a href="/profile" className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-100 transition">
                    <span>👤</span> Profile
                  </a>
                  <a href="/orders" className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-100 transition">
                    <span>📦</span> Orders & Refunds
                  </a>
                  <a href="/watchlist" className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-100 transition">
                    <span>♡</span> Watchlist
                  </a>
                  <a href="/settings" className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-100 transition">
                    <span>⚙️</span> Settings
                  </a>
                  <a href="/auth" className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-100 text-rose-600 transition">
                    <span>🔐</span> Sign Out
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Category Strip */}
      <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-1.5 overflow-x-auto">
        <div className="mx-auto flex max-w-7xl items-center gap-1 text-[11px] font-semibold text-slate-600">
          <span className="text-slate-400 font-bold uppercase tracking-wider text-[10px] mr-2">
            Categories:
          </span>
          {NAV_CATEGORIES.map((c) => (
            <a
              key={c.name}
              href={c.href}
              className="rounded-lg px-2.5 py-1 hover:bg-white hover:text-slate-950 hover:shadow-2xs transition whitespace-nowrap"
            >
              {c.name}
            </a>
          ))}
        </div>
      </div>
    </header>
  );
}

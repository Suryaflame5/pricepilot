"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCart } from "@/lib/cartContext";
import { useOrders } from "@/lib/orderContext";
import { inr } from "@/lib/formatting";
import { getRetailerMeta } from "@/lib/retailers";

export default function CartPage() {
  const router = useRouter();
  const { items, removeItem, updateQuantity, clearCart, subtotal, totalSavings } = useCart();
  const { placeOrder } = useOrders();

  const [promoCode, setPromoCode] = useState("");
  const [promoDiscount, setPromoDiscount] = useState(0);
  const [promoMessage, setPromoMessage] = useState<string | null>(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [orderSuccess, setOrderSuccess] = useState<string | null>(null);

  const applyPromo = (e: React.FormEvent) => {
    e.preventDefault();
    const code = promoCode.trim().toUpperCase();
    if (code === "PRICEPILOT50") {
      setPromoDiscount(50);
      setPromoMessage("₹50 discount applied successfully!");
    } else if (code === "FESTIVAL100") {
      setPromoDiscount(100);
      setPromoMessage("₹100 Festive discount applied!");
    } else {
      setPromoMessage("Invalid promo code. Try PRICEPILOT50 or FESTIVAL100");
    }
  };

  const finalTotal = Math.max(0, subtotal - promoDiscount);

  const handleCheckout = () => {
    if (items.length === 0) return;
    setIsCheckingOut(true);

    setTimeout(() => {
      const primaryRetailer = items[0]?.retailer || "Flipkart";
      const createdOrder = placeOrder(items, primaryRetailer, finalTotal);
      clearCart();
      setIsCheckingOut(false);
      setOrderSuccess(createdOrder.orderNumber);
    }, 1200);
  };

  if (orderSuccess) {
    return (
      <div className="mx-auto max-w-xl py-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 mb-4 shadow-sm">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-2xl font-black text-slate-900">Order Placed Successfully!</h1>
        <p className="mt-2 text-sm text-slate-600">
          Order Reference: <strong className="text-slate-900">{orderSuccess}</strong>
        </p>
        <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-800">
          🛡️ <strong>7-Day Price Drop Protection Activated!</strong> If the price drops on any tracked platform within 7 days, PricePilot will automatically notify you and process a price-match refund.
        </div>
        <div className="mt-6 flex flex-col sm:flex-row justify-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/orders")}
            className="rounded-xl bg-slate-900 px-6 py-2.5 text-xs font-bold text-white hover:bg-brand-600 transition"
          >
            Track My Order & Refunds →
          </button>
          <button
            type="button"
            onClick={() => router.push("/")}
            className="rounded-xl border border-slate-300 bg-white px-6 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 transition"
          >
            Continue Shopping
          </button>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-slate-100 text-slate-400 mb-4">
          <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        </div>
        <h1 className="text-xl font-black text-slate-900">Your Shopping Cart is Empty</h1>
        <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto">
          Scan any product across Amazon, Flipkart, Meesho, and Myntra. Add items to track the lowest checkout prices and activate automatic price protection.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <a
            href="/"
            className="rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-brand-600 transition"
          >
            Explore Featured Deals
          </a>
          <a
            href="/search"
            className="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 transition"
          >
            Search Any Product
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900">Shopping Cart</h1>
          <p className="text-xs text-slate-500">
            {items.length} item{items.length === 1 ? "" : "s"} selected with Multi-Retailer Price Protection
          </p>
        </div>
        <button
          type="button"
          onClick={clearCart}
          className="text-xs font-semibold text-rose-600 hover:underline"
        >
          Clear Cart
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Item List */}
        <div className="lg:col-span-2 space-y-4">
          {/* Smart Retailer Optimization Callout */}
          <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50/80 to-purple-50/80 p-4 text-xs">
            <div className="flex items-center gap-2 font-bold text-indigo-900">
              <span>⚡</span>
              <span>Smart Retailer Engine Active</span>
            </div>
            <p className="mt-1 text-slate-600 leading-relaxed">
              PricePilot automatically aggregates prices across <strong>Flipkart, Amazon India, Meesho, Myntra, Nykaa, and Croma</strong> to ensure you get the absolute lowest checked-out price.
            </p>
          </div>

          {/* Cart Item Cards */}
          <div className="space-y-3">
            {items.map((item) => {
              const meta = getRetailerMeta(item.retailer);

              return (
                <div
                  key={item.id}
                  className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl bg-slate-50 p-1 border border-slate-100">
                      <img src={item.image} alt={item.name} className="h-full w-full object-contain" />
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.badgeColor}`}>
                          {item.retailer}
                        </span>
                        {item.brand && <span className="text-[11px] font-semibold text-slate-400">{item.brand}</span>}
                      </div>
                      <h3 className="font-bold text-sm text-slate-900 truncate max-w-sm">{item.name}</h3>
                      <p className="text-[11px] text-emerald-600 font-medium">✓ In Stock • {meta.deliveryEstimate}</p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between w-full sm:w-auto sm:justify-end gap-6 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                    {/* Quantity Selector */}
                    <div className="flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, item.quantity - 1)}
                        className="h-6 w-6 flex items-center justify-center rounded-lg text-slate-600 hover:bg-white text-xs font-bold transition"
                      >
                        -
                      </button>
                      <span className="w-8 text-center text-xs font-bold text-slate-800">{item.quantity}</span>
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, item.quantity + 1)}
                        className="h-6 w-6 flex items-center justify-center rounded-lg text-slate-600 hover:bg-white text-xs font-bold transition"
                      >
                        +
                      </button>
                    </div>

                    {/* Price Display */}
                    <div className="text-right min-w-[90px]">
                      <div className="font-black text-sm text-slate-900">{inr(item.price * item.quantity)}</div>
                      {item.originalPrice && item.originalPrice > item.price && (
                        <div className="text-[11px] text-slate-400 line-through">
                          {inr(item.originalPrice * item.quantity)}
                        </div>
                      )}
                    </div>

                    {/* Delete button */}
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="text-slate-400 hover:text-rose-600 p-1 transition"
                      title="Remove from Cart"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Checkout Summary */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <h2 className="font-bold text-sm uppercase tracking-wider text-slate-900 border-b border-slate-100 pb-3">
              Order Summary
            </h2>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-slate-600">
                <span>Items Subtotal:</span>
                <span className="font-semibold text-slate-900">{inr(subtotal)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Shipping & Delivery:</span>
                <span className="font-semibold text-emerald-600">FREE</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>7-Day Price Guarantee:</span>
                <span className="font-semibold text-emerald-600">FREE INCLUDED</span>
              </div>
              {promoDiscount > 0 && (
                <div className="flex justify-between text-emerald-600 font-bold">
                  <span>Promo Discount:</span>
                  <span>- {inr(promoDiscount)}</span>
                </div>
              )}
              {totalSavings > 0 && (
                <div className="flex justify-between text-rose-600 font-medium">
                  <span>Total Savings vs MRP:</span>
                  <span>- {inr(totalSavings)}</span>
                </div>
              )}
              <div className="border-t border-slate-100 pt-3 flex justify-between items-baseline">
                <span className="font-black text-sm text-slate-900">Total Payable:</span>
                <span className="text-xl font-black text-slate-900">{inr(finalTotal)}</span>
              </div>
            </div>

            {/* Promo Code Input */}
            <form onSubmit={applyPromo} className="border-t border-slate-100 pt-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value)}
                  placeholder="Promo Code (PRICEPILOT50)"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs uppercase placeholder:normal-case focus:border-brand-500 focus:bg-white focus:outline-none"
                />
                <button
                  type="submit"
                  className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-brand-600 transition"
                >
                  Apply
                </button>
              </div>
              {promoMessage && (
                <p className="mt-1.5 text-[11px] font-medium text-emerald-600">{promoMessage}</p>
              )}
            </form>

            {/* Checkout Action Button */}
            <button
              type="button"
              disabled={isCheckingOut}
              onClick={handleCheckout}
              className="w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 py-3 text-sm font-bold text-white shadow-md hover:from-emerald-500 hover:to-teal-500 transition disabled:opacity-50"
            >
              {isCheckingOut ? "Processing Instant Order..." : `Proceed to Checkout • ${inr(finalTotal)}`}
            </button>

            <div className="rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500 leading-relaxed border border-slate-100">
              🔒 Safe & Secure Checkout with instant price drop claim tracking and 7-day refund policy.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useOrders, type OrderStatus } from "@/lib/orderContext";
import { inr } from "@/lib/formatting";
import { getRetailerMeta } from "@/lib/retailers";

const TRACKING_STEPS: { key: OrderStatus; label: string }[] = [
  { key: "confirmed", label: "Confirmed" },
  { key: "shipped", label: "Shipped" },
  { key: "in_transit", label: "In Transit" },
  { key: "out_for_delivery", label: "Out for Delivery" },
  { key: "delivered", label: "Delivered" },
];

function getStepIndex(status: OrderStatus): number {
  return TRACKING_STEPS.findIndex((s) => s.key === status);
}

export default function OrdersPage() {
  const { orders, claimPriceDropRefund } = useOrders();
  const [selectedOrder, setSelectedOrder] = useState<string | null>(null);
  const [claimSuccess, setClaimSuccess] = useState<string | null>(null);

  const handleClaim = (orderId: string, amount: number) => {
    claimPriceDropRefund(orderId, amount);
    setClaimSuccess(`₹${amount} Price Drop Refund successfully credited to your payment method!`);
    setTimeout(() => setClaimSuccess(null), 4000);
  };

  const totalRefundsClaimed = orders.reduce(
    (sum, o) => sum + (o.priceDropRefundClaimed ? (o.priceDropRefundAmount || 850) : 0),
    0
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900">Orders & Price Protection</h1>
          <p className="text-xs text-slate-500">
            Track multi-retailer shipments and claim automatic price drop refunds
          </p>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-right">
          <div className="text-[10px] uppercase font-bold tracking-wider text-emerald-700">
            Total Price Drop Refunds Claimed
          </div>
          <div className="text-lg font-black text-emerald-800">{inr(totalRefundsClaimed)}</div>
        </div>
      </div>

      {claimSuccess && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-xs font-bold text-emerald-800 flex items-center gap-2">
          <span>🎉</span>
          <span>{claimSuccess}</span>
        </div>
      )}

      {orders.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-sm text-slate-500">No orders placed yet.</p>
          <a
            href="/"
            className="mt-4 inline-block rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-brand-600 transition"
          >
            Start Shopping
          </a>
        </div>
      ) : (
        <div className="space-y-6">
          {orders.map((order) => {
            const meta = getRetailerMeta(order.retailer);
            const currentStepIdx = getStepIndex(order.status);

            return (
              <div
                key={order.id}
                className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md"
              >
                {/* Order Top Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/70 px-6 py-4 text-xs">
                  <div className="flex items-center gap-4">
                    <div>
                      <span className="text-slate-400">Order Placed:</span>{" "}
                      <strong className="text-slate-800">{order.date}</strong>
                    </div>
                    <div>
                      <span className="text-slate-400">Order ID:</span>{" "}
                      <strong className="text-slate-800">{order.orderNumber}</strong>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 font-bold text-[11px] ${meta.badgeColor}`}>
                      {order.retailer}
                    </span>
                    <span className="font-black text-sm text-slate-900">{inr(order.total)}</span>
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {/* Delivery Status Stepper */}
                  <div>
                    <div className="flex items-center justify-between text-xs mb-3">
                      <div>
                        <span className="font-bold text-slate-900">Status: </span>
                        <span className="capitalize font-semibold text-brand-600">
                          {order.status.replace(/_/g, " ")}
                        </span>
                        <span className="text-slate-400 ml-2">({order.estimatedDelivery})</span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {order.carrier} • Tracking: <span className="font-mono font-bold text-slate-800">{order.trackingNumber}</span>
                      </div>
                    </div>

                    {/* Progress Track */}
                    <div className="grid grid-cols-5 gap-1.5">
                      {TRACKING_STEPS.map((step, idx) => {
                        const isDone = idx <= currentStepIdx;
                        return (
                          <div key={step.key} className="space-y-1">
                            <div
                              className={`h-2 rounded-full transition-all ${
                                isDone ? "bg-emerald-500" : "bg-slate-200"
                              }`}
                            />
                            <div
                              className={`text-[10px] font-bold text-center ${
                                isDone ? "text-emerald-700" : "text-slate-400"
                              }`}
                            >
                              {step.label}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Order Items */}
                  <div className="space-y-3 pt-2">
                    {order.items.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between gap-4 rounded-2xl bg-slate-50 p-3 border border-slate-100">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-xl bg-white p-1 border border-slate-200">
                            <img src={item.image} alt={item.name} className="h-full w-full object-contain" />
                          </div>
                          <div className="min-w-0">
                            <div className="font-bold text-xs text-slate-900 truncate max-w-md">{item.name}</div>
                            {item.variantName && <div className="text-[11px] text-slate-500">{item.variantName}</div>}
                            <div className="text-[11px] text-slate-400">Qty: {item.quantity} • Fulfilled by {item.retailer}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-black text-xs text-slate-900">{inr(item.price * item.quantity)}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Price Protection Guarantee & Refund Section */}
                  <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50/60 to-purple-50/60 p-4">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-900">
                          <span>🛡️</span>
                          <span>PricePilot 7-Day Price Drop Protection Active</span>
                        </div>
                        <p className="mt-0.5 text-[11px] text-slate-600">
                          Our continuous scraper monitors this product daily across all competitor stores. If a cheaper offer surfaces within 7 days, you get the difference refunded.
                        </p>
                      </div>

                      {order.priceDropRefundClaimed ? (
                        <span className="inline-flex items-center gap-1 rounded-xl bg-emerald-100 px-3.5 py-1.5 text-xs font-bold text-emerald-800">
                          ✓ ₹{order.priceDropRefundAmount || 850} Refund Claimed
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleClaim(order.id, 850)}
                          className="flex-shrink-0 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-indigo-500 transition"
                        >
                          Claim ₹850 Price-Match Refund ⚡
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

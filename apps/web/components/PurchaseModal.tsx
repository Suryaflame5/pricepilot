"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { inr } from "@/lib/formatting";
import type {
  CheckoutReady,
  OrderPlaced,
  PriceVerification,
  ShoppingSession,
  ShoppingSessionWithOffers,
} from "@/lib/types";

interface Props {
  isOpen: boolean;
  variantId: string;
  productName: string;
  initialListingId?: string | null;
  onClose: () => void;
}

type Step = "SELECT" | "VERIFIED" | "CHECKOUT" | "ORDERED" | "ERROR";

export default function PurchaseModal({
  isOpen,
  variantId,
  productName,
  initialListingId,
  onClose,
}: Props) {
  const [step, setStep] = useState<Step>("SELECT");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [session, setSession] = useState<ShoppingSession | null>(null);
  const [offers, setOffers] = useState<ShoppingSessionWithOffers["offers"]>([]);
  const [selectedListingId, setSelectedListingId] = useState<string | null>(initialListingId ?? null);
  const [verification, setVerification] = useState<PriceVerification | null>(null);
  const [checkout, setCheckout] = useState<CheckoutReady | null>(null);
  const [order, setOrder] = useState<OrderPlaced | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setStep("SELECT");
      setSession(null);
      setVerification(null);
      setCheckout(null);
      setOrder(null);
      setError(null);
      return;
    }

    async function initSession() {
      setLoading(true);
      setError(null);
      try {
        const s = await post<ShoppingSessionWithOffers>("/shopping-sessions", {
          product_variant_id: variantId,
          strategy: "IMMEDIATE",
        });
        setSession(s);
        setOffers(s.offers || []);

        const targetListing = initialListingId || s.selected_listing_id || (s.offers?.[0]?.listing_id);
        if (targetListing) {
          setSelectedListingId(targetListing);
          await selectAndVerify(s.id, targetListing);
        } else {
          setStep("SELECT");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to initiate shopping session");
        setStep("ERROR");
      } finally {
        setLoading(false);
      }
    }

    initSession();
  }, [isOpen, variantId, initialListingId]);

  async function selectAndVerify(sessionId: string, listingId: string) {
    setLoading(true);
    setError(null);
    try {
      await post(`/shopping-sessions/${sessionId}/select`, { listing_id: listingId });
      const ver = await post<PriceVerification>(`/shopping-sessions/${sessionId}/verify-price`, {});
      setVerification(ver);
      setStep("VERIFIED");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to verify offer price");
      setStep("ERROR");
    } finally {
      setLoading(false);
    }
  }

  async function confirmOffer() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const cr = await post<CheckoutReady>(`/shopping-sessions/${session.id}/confirm`, { accept: true });
      setCheckout(cr);
      setStep("CHECKOUT");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm offer selection");
    } finally {
      setLoading(false);
    }
  }

  async function placeOrder() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const placed = await post<OrderPlaced>(`/shopping-sessions/${session.id}/place-order`, { confirmed: true });
      setOrder(placed);
      setStep("ORDERED");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to place order (price may have drifted)");
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  const currentOffer = offers.find((o) => o.listing_id === selectedListingId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-600">
              Two-Confirmation Purchase
            </span>
            <h2 className="text-base font-bold text-slate-900 line-clamp-1">{productName}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <span className="font-semibold">Notice: </span>
              {error}
            </div>
          )}

          {loading && (
            <div className="my-8 flex flex-col items-center justify-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
              <p className="text-xs text-slate-500 font-medium">Verifying live price & provider status...</p>
            </div>
          )}

          {!loading && step === "SELECT" && (
            <div>
              <p className="mb-3 text-xs font-medium text-slate-500">Select retailer offer to proceed:</p>
              <div className="space-y-2">
                {offers.map((o) => (
                  <button
                    key={o.listing_id}
                    type="button"
                    onClick={() => {
                      setSelectedListingId(o.listing_id);
                      if (session) selectAndVerify(session.id, o.listing_id);
                    }}
                    className="flex w-full items-center justify-between rounded-xl border border-slate-200 p-3 text-left transition hover:border-brand-500 hover:bg-slate-50"
                  >
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{o.retailer_name}</div>
                      {o.delivery_days != null && (
                        <div className="text-xs text-slate-500">Delivered in ~{o.delivery_days} days</div>
                      )}
                    </div>
                    <div className="text-right font-bold text-slate-900">{inr(o.effective_price)}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {!loading && step === "VERIFIED" && verification && (
            <div className="space-y-4">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase text-emerald-800">
                    Step 1: Offer Verified
                  </span>
                  <span className="rounded-full bg-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-900">
                    Price Validated
                  </span>
                </div>
                <div className="mt-3 flex items-baseline justify-between">
                  <span className="text-sm font-medium text-slate-700">
                    {currentOffer?.retailer_name || "Selected Retailer"}
                  </span>
                  <span className="text-2xl font-bold text-slate-900 tabular-nums">
                    {inr(verification.current_effective_price ?? currentOffer?.effective_price)}
                  </span>
                </div>
                {verification.price_changed && (
                  <p className="mt-2 text-xs text-amber-700">
                    ⚠ Price changed from {inr(verification.previous_effective_price)} to{" "}
                    {inr(verification.current_effective_price)} since last check.
                  </p>
                )}
              </div>

              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                <p>
                  <strong>First Confirmation:</strong> You are confirming offer selection with{" "}
                  <strong>{currentOffer?.retailer_name}</strong>. No payment will be executed yet.
                </p>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 rounded-xl border border-slate-300 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={confirmOffer}
                  className="flex-1 rounded-xl bg-brand-600 py-2.5 text-xs font-semibold text-white shadow hover:bg-brand-700"
                >
                  Confirm Offer Selection
                </button>
              </div>
            </div>
          )}

          {!loading && step === "CHECKOUT" && checkout && (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase text-slate-500">
                    Step 2: Final Purchase Review
                  </span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                    Checkout Ready
                  </span>
                </div>

                <div className="mt-4 space-y-2 border-b border-slate-200 pb-3 text-sm">
                  <div className="flex justify-between text-slate-600">
                    <span>Retailer Provider</span>
                    <span className="font-medium text-slate-900">{currentOffer?.retailer_name}</span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>Delivery Estimate</span>
                    <span className="font-medium text-slate-900">
                      {checkout.delivery_estimate || "Standard (2-4 business days)"}
                    </span>
                  </div>
                </div>

                <div className="mt-3 flex items-baseline justify-between">
                  <span className="text-sm font-bold text-slate-900">Final Total</span>
                  <span className="text-2xl font-bold text-slate-900 tabular-nums">
                    {inr(checkout.checkout_total ?? currentOffer?.effective_price)}
                  </span>
                </div>
              </div>

              <p className="text-[11px] text-slate-500">
                Live price verification will re-check the database immediately before authorizing.
                Any price drift &gt; 0.5% will abort purchase.
              </p>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setStep("VERIFIED")}
                  className="flex-1 rounded-xl border border-slate-300 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={placeOrder}
                  className="flex-1 rounded-xl bg-emerald-600 py-2.5 text-xs font-semibold text-white shadow hover:bg-emerald-700"
                >
                  Authorize & Place Order
                </button>
              </div>
            </div>
          )}

          {!loading && step === "ORDERED" && order && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                ✓
              </div>
              <h3 className="text-lg font-bold text-slate-900">Order Placed Successfully!</h3>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-left text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">Order Reference</span>
                  <span className="font-mono font-bold text-slate-800">{order.order_ref}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Retailer</span>
                  <span className="font-semibold text-slate-800">{order.retailer_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Total Paid</span>
                  <span className="font-bold text-slate-900 tabular-nums">{inr(order.total)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Status</span>
                  <span className="font-medium text-emerald-600 uppercase">{order.status}</span>
                </div>
              </div>

              {order.tracking_url && (
                <a
                  href={order.tracking_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-xs font-medium text-brand-600 hover:underline"
                >
                  Track Order Online →
                </a>
              )}

              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-xl bg-slate-900 py-2.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useRef, useState } from "react";
import { num } from "@/lib/realtime";
import { useRealtimeSubscription } from "@/lib/useRealtime";

export const LIVE_TOPICS = [
  "price.changed",
  "price.dropped",
  "price.spike",
  "stock.changed",
  "promotion.started",
  "promotion.ended",
  "prediction.updated",
  "decision.changed",
  "alert.triggered",
];

export interface LivePriceState {
  /** live observed effective price for this listing */
  price: number | null;
  from: number | null;
  to: number | null;
  retailerName: string | null;
  updatedAt: number | null;
}

interface Options {
  onPredictionUpdated?: () => void;
  onDecisionChanged?: (payload: Record<string, unknown>) => void;
  onAlertTriggered?: () => void;
}

/**
 * Live incremental layer for the product page. REST provides the snapshot;
 * this hook only APPLIES server-sent events — it never computes intelligence.
 */
export function useLiveProduct(
  variantId: string | undefined,
  listingId: string | undefined,
  opts: Options = {}
): LivePriceState {
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const [live, setLive] = useState<LivePriceState>({
    price: null,
    from: null,
    to: null,
    retailerName: null,
    updatedAt: null,
  });

  useRealtimeSubscription(
    LIVE_TOPICS,
    [variantId, listingId].filter((x): x is string => Boolean(x)),
    (eventType, env) => {
      const payload = env.payload;
      const isListing = env.aggregate_id === listingId || payload.listing_id === listingId;
      const isVariant = env.aggregate_id === variantId || payload.product_variant_id === variantId;

      if (eventType.startsWith("price.") && isListing) {
        const to = num(payload.to ?? payload.effective_price);
        const from = num(payload.from);
        setLive((prev) => ({
          price: to,
          from: from ?? prev.price ?? prev.from,
          to,
          retailerName:
            typeof payload.retailer_name === "string" ? payload.retailer_name : prev.retailerName,
          updatedAt: Date.now(),
        }));
      }
      if (eventType === "prediction.updated" && isVariant) {
        optsRef.current.onPredictionUpdated?.();
      }
      if (eventType === "decision.changed" && isVariant) {
        optsRef.current.onDecisionChanged?.(payload);
      }
      if (eventType === "alert.triggered" && isVariant) {
        optsRef.current.onAlertTriggered?.();
      }
    }
  );

  return live;
}
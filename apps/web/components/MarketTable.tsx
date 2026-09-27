"use client";

import type { RetailerOffer } from "@/lib/types";
import OfferRow from "./OfferRow";
import { inr } from "@/lib/formatting";

interface Props {
  offers: RetailerOffer[];
  cheapestListingId?: string | null;
  onBuyOffer?: ((listingId: string) => void) | null;
}

/** MARKET section: all trusted offers, cheapest first, best flagged. */
export default function MarketTable({ offers, cheapestListingId, onBuyOffer }: Props) {
  if (offers.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 shadow-sm">
        No trusted offers available right now.
      </div>
    );
  }
  const sorted = [...offers].sort(
    (a, b) => (a.effective_price ?? Infinity) - (b.effective_price ?? Infinity)
  );
  return (
    <div className="space-y-2">
      {sorted.map((o) => (
        <OfferRow
          key={o.listing_id}
          retailer={o.retailer_name}
          effectivePrice={o.effective_price}
          availability={o.availability}
          url={o.url}
          best={cheapestListingId != null ? o.listing_id === cheapestListingId : o.effective_price === sorted[0].effective_price}
          onBuy={onBuyOffer ? () => onBuyOffer(o.listing_id) : null}
        />
      ))}
      <div className="px-1 text-[11px] tracking-wide text-slate-400">
        {offers.length} TRUSTED OFFER{offers.length === 1 ? "" : "S"} · LOWEST {inr(sorted[0].effective_price)}
      </div>
    </div>
  );
}
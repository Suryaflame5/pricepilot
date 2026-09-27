"use client";

import { useState } from "react";
import type { ProductImageSet } from "@/lib/productImages";
import { getRetailerMeta } from "@/lib/retailers";

interface ProductGalleryProps {
  imageSet: ProductImageSet;
  productName: string;
  category?: string;
  retailerName?: string;
  discountPct?: number;
}

export default function ProductGallery({
  imageSet,
  productName,
  category,
  retailerName,
  discountPct,
}: ProductGalleryProps) {
  const [activeImage, setActiveImage] = useState(imageSet.primary);
  const retailer = getRetailerMeta(retailerName);

  return (
    <div className="flex flex-col gap-4">
      {/* Main Feature Display */}
      <div className="group relative aspect-square w-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
        {/* Top Badges */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2">
          {category && (
            <span className="rounded-full bg-slate-900/80 backdrop-blur-sm px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-white">
              {category.replace(/-/g, " ")}
            </span>
          )}
          {discountPct != null && discountPct > 0 && (
            <span className="rounded-full bg-rose-600 px-2.5 py-1 text-xs font-bold text-white shadow-sm">
              {Math.round(discountPct)}% OFF
            </span>
          )}
        </div>

        {/* Retailer Source Tag */}
        <div className="absolute top-4 right-4 z-10">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold shadow-sm ${retailer.badgeColor}`}
          >
            {retailer.badge}
          </span>
        </div>

        {/* Hero Photo with zoom hover */}
        <img
          src={activeImage}
          alt={productName}
          className="h-full w-full object-contain transition duration-500 group-hover:scale-105"
        />

        {/* Bottom Guarantee Banner */}
        <div className="absolute bottom-3 inset-x-3 rounded-xl bg-slate-900/90 backdrop-blur-md px-3 py-1.5 text-center text-[11px] font-medium text-slate-200">
          🛡️ Verified Authentic Multi-Retailer Product • 7-Day Price Drop Protection
        </div>
      </div>

      {/* Alternative Angles Thumbnails */}
      {imageSet.gallery && imageSet.gallery.length > 1 && (
        <div className="flex items-center gap-2.5 overflow-x-auto pb-1">
          {imageSet.gallery.map((img, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setActiveImage(img)}
              className={`relative h-18 w-18 flex-shrink-0 overflow-hidden rounded-xl border-2 bg-white p-1.5 transition ${
                activeImage === img
                  ? "border-brand-600 ring-2 ring-brand-500/20 shadow-sm"
                  : "border-slate-200 hover:border-slate-300 opacity-80 hover:opacity-100"
              }`}
            >
              <img src={img} alt={`${productName} thumbnail ${idx + 1}`} className="h-full w-full object-contain" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Retailer metadata, official branding colors, badges, and trust tags.

export interface RetailerMeta {
  id: string;
  name: string;
  displayName: string;
  tagline: string;
  badge: string;
  badgeColor: string;
  brandBg: string;
  brandText: string;
  accentBorder: string;
  deliveryEstimate: string;
  codAvailable: boolean;
  returnPolicy: string;
  logoShort: string;
  topCategories: string[];
}

export const RETAILER_METADATA: Record<string, RetailerMeta> = {
  flipkart: {
    id: "flipkart",
    name: "flipkart",
    displayName: "Flipkart",
    tagline: "India's Shopping Destination",
    badge: "Flipkart Assured",
    badgeColor: "bg-blue-600 text-white",
    brandBg: "bg-blue-50 text-blue-800",
    brandText: "text-blue-600",
    accentBorder: "border-blue-400",
    deliveryEstimate: "2 - 3 Days Delivery",
    codAvailable: true,
    returnPolicy: "7 Days Replacement",
    logoShort: "FK",
    topCategories: ["Electronics", "Mobiles", "Fashion", "Appliances"],
  },
  amazon: {
    id: "amazon",
    name: "amazon",
    displayName: "Amazon India",
    tagline: "Fast & Free Prime Delivery",
    badge: "Prime Fulfilled",
    badgeColor: "bg-amber-500 text-slate-900 font-bold",
    brandBg: "bg-amber-50 text-amber-900",
    brandText: "text-amber-600",
    accentBorder: "border-amber-400",
    deliveryEstimate: "Tomorrow by 9 PM",
    codAvailable: true,
    returnPolicy: "10 Days Returnable",
    logoShort: "AMZ",
    topCategories: ["All Categories", "Books", "Electronics", "Pantry"],
  },
  meesho: {
    id: "meesho",
    name: "meesho",
    displayName: "Meesho",
    tagline: "Lowest Wholesale Prices Guaranteed",
    badge: "Lowest Price Tag",
    badgeColor: "bg-fuchsia-700 text-white",
    brandBg: "bg-fuchsia-50 text-fuchsia-800",
    brandText: "text-fuchsia-700",
    accentBorder: "border-fuchsia-400",
    deliveryEstimate: "4 - 5 Days Free Shipping",
    codAvailable: true,
    returnPolicy: "7 Days Easy Return",
    logoShort: "MSH",
    topCategories: ["Fashion", "Home Decor", "Kitchen", "Daily Needs"],
  },
  myntra: {
    id: "myntra",
    name: "myntra",
    displayName: "Myntra",
    tagline: "100% Original Premium Fashion",
    badge: "Style Assured",
    badgeColor: "bg-gradient-to-r from-pink-500 to-rose-500 text-white",
    brandBg: "bg-rose-50 text-rose-800",
    brandText: "text-rose-600",
    accentBorder: "border-rose-400",
    deliveryEstimate: "2 - 3 Days Express",
    codAvailable: true,
    returnPolicy: "14 Days Hassle-Free Returns",
    logoShort: "MYN",
    topCategories: ["Fashion", "Sneakers", "Apparel", "Watches"],
  },
  nykaa: {
    id: "nykaa",
    name: "nykaa",
    displayName: "Nykaa",
    tagline: "India's Premier Beauty & Wellness",
    badge: "100% Authentic Beauty",
    badgeColor: "bg-pink-600 text-white",
    brandBg: "bg-pink-50 text-pink-800",
    brandText: "text-pink-600",
    accentBorder: "border-pink-400",
    deliveryEstimate: "1 - 2 Days Delivery",
    codAvailable: true,
    returnPolicy: "15 Days Authenticity Guarantee",
    logoShort: "NYK",
    topCategories: ["Beauty", "Skincare", "Cosmetics", "Fragrances"],
  },
  croma: {
    id: "croma",
    name: "croma",
    displayName: "Croma",
    tagline: "A Tata Enterprise Electronics Hub",
    badge: "Tata Assured",
    badgeColor: "bg-teal-600 text-white",
    brandBg: "bg-teal-50 text-teal-800",
    brandText: "text-teal-600",
    accentBorder: "border-teal-400",
    deliveryEstimate: "3-Hour Store Pickup / 2 Days",
    codAvailable: false,
    returnPolicy: "Brand Warranty + Croma Care",
    logoShort: "CRO",
    topCategories: ["Laptops", "Appliances", "Smartphones", "Audio"],
  },
  "reliance-digital": {
    id: "reliance-digital",
    name: "reliance digital",
    displayName: "Reliance Digital",
    tagline: "Personalising Technology",
    badge: "InstaDelivery",
    badgeColor: "bg-red-600 text-white",
    brandBg: "bg-red-50 text-red-800",
    brandText: "text-red-600",
    accentBorder: "border-red-400",
    deliveryEstimate: "Same-Day / Next-Day Delivery",
    codAvailable: true,
    returnPolicy: "ResQ Expert Installation",
    logoShort: "RD",
    topCategories: ["Televisions", "Laptops", "Refrigerators", "Gadgets"],
  },
};

export function getRetailerMeta(retailerName?: string | null): RetailerMeta {
  if (!retailerName) return RETAILER_METADATA.amazon;
  const key = retailerName.toLowerCase().replace(/[^a-z]/g, "");
  for (const [id, meta] of Object.entries(RETAILER_METADATA)) {
    if (key.includes(id) || key.includes(meta.name.replace(/[^a-z]/g, ""))) {
      return meta;
    }
  }
  return {
    id: "retailer",
    name: retailerName,
    displayName: retailerName,
    tagline: "Verified E-Commerce Store",
    badge: "Verified Retailer",
    badgeColor: "bg-slate-700 text-white",
    brandBg: "bg-slate-100 text-slate-800",
    brandText: "text-slate-700",
    accentBorder: "border-slate-300",
    deliveryEstimate: "2 - 4 Business Days",
    codAvailable: true,
    returnPolicy: "Standard Return Policy",
    logoShort: retailerName.slice(0, 3).toUpperCase(),
    topCategories: ["All Products"],
  };
}

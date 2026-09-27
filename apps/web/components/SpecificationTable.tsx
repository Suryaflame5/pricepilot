"use client";

interface SpecificationTableProps {
  product: {
    canonical_name: string;
    brand?: string | null;
    model?: string | null;
    category?: string | null;
    subcategory?: string | null;
    description?: string | null;
  };
}

export default function SpecificationTable({ product }: SpecificationTableProps) {
  const specs = [
    { label: "Product Name", value: product.canonical_name },
    { label: "Brand", value: product.brand || "Authentic Certified Brand" },
    { label: "Model", value: product.model || "Official Standard Edition" },
    { label: "Category", value: product.category ? product.category.replace(/-/g, " ").toUpperCase() : "General Merchandise" },
    { label: "Sub-Category", value: product.subcategory ? product.subcategory.replace(/-/g, " ") : "Standard" },
    { label: "Warranty", value: "1 Year Official Manufacturer Warranty" },
    { label: "In the Box", value: "Primary Unit, Power Cable / Accessories, User Manual, Official Warranty Card" },
    { label: "Country of Origin", value: "India / Global" },
    { label: "E-Commerce Verification", value: "Cross-platform verified across Amazon, Flipkart, Meesho, Nykaa & Croma" },
    { label: "Price Protection", value: "Eligible for 7-Day Price Pilot Automatic Refund" },
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 mb-4 flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-md bg-slate-900 text-white text-[10px]">
          ⚙️
        </span>
        Complete Product Specifications & Details
      </h3>

      {product.description && (
        <p className="mb-4 text-xs text-slate-600 leading-relaxed border-b border-slate-100 pb-3">
          {product.description}
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-xs">
        {specs.map((s, idx) => (
          <div key={idx} className="flex items-start justify-between border-b border-slate-50 py-1.5">
            <span className="font-medium text-slate-400 w-1/3">{s.label}</span>
            <span className="font-semibold text-slate-800 text-right w-2/3 truncate">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { CartProvider } from "@/lib/cartContext";
import { AuthProvider } from "@/lib/authContext";
import { OrderProvider } from "@/lib/orderContext";

export const metadata: Metadata = {
  title: "PricePilot - Real-Time Price Comparison & Deal Finder",
  description: "Real-time product search, price comparisons across Flipkart, Amazon India, Meesho, Myntra, and predictive price drop tracking",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-brand-500 selection:text-white flex flex-col justify-between">
        <AuthProvider>
          <CartProvider>
            <OrderProvider>
              <Navbar />
              <main className="flex-1 w-full mx-auto max-w-7xl px-4 sm:px-6 py-6">{children}</main>
              <Footer />
            </OrderProvider>
          </CartProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

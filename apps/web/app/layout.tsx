import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { CartProvider } from "@/lib/cartContext";
import { AuthProvider } from "@/lib/authContext";
import { OrderProvider } from "@/lib/orderContext";

export const metadata: Metadata = {
  title: "ShoppingOS — Universal Price Intelligence & Deals Terminal",
  description: "Search any product in India. Real-time live price comparison across Amazon India, Flipkart, Meesho, Croma, and Reliance Digital with 90% conformal price drop forecasting.",
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

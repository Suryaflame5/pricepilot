"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import type { CartItem } from "./cartContext";

export type OrderStatus = "confirmed" | "shipped" | "in_transit" | "out_for_delivery" | "delivered";

export interface OrderItem {
  name: string;
  image: string;
  retailer: string;
  price: number;
  quantity: number;
  variantName?: string;
}

export interface Order {
  id: string;
  orderNumber: string;
  date: string;
  retailer: string;
  status: OrderStatus;
  estimatedDelivery: string;
  items: OrderItem[];
  subtotal: number;
  shipping: number;
  discount: number;
  total: number;
  trackingNumber: string;
  carrier: string;
  priceDropRefundClaimed?: boolean;
  priceDropRefundAmount?: number;
}

interface OrderContextType {
  orders: Order[];
  placeOrder: (cartItems: CartItem[], retailer: string, total: number) => Order;
  claimPriceDropRefund: (orderId: string, refundAmount: number) => void;
}

const INITIAL_ORDERS: Order[] = [
  {
    id: "ord_10283",
    orderNumber: "PP-984210",
    date: "24 Sep 2026",
    retailer: "Flipkart",
    status: "out_for_delivery",
    estimatedDelivery: "Today, by 8:00 PM",
    trackingNumber: "FMPC098234821",
    carrier: "Ekart Logistics Express",
    subtotal: 31999,
    shipping: 0,
    discount: 1500,
    total: 30499,
    priceDropRefundClaimed: true,
    priceDropRefundAmount: 850,
    items: [
      {
        name: "Apple Watch Series 9 GPS 41mm Midnight Aluminium",
        image: "https://images.unsplash.com/photo-1546868871-7041f2a55e12?auto=format&fit=crop&w=800&q=80",
        retailer: "Flipkart",
        price: 30499,
        quantity: 1,
        variantName: "41mm Midnight",
      },
    ],
  },
  {
    id: "ord_10284",
    orderNumber: "PP-872911",
    date: "20 Sep 2026",
    retailer: "Amazon India",
    status: "delivered",
    estimatedDelivery: "Delivered on 22 Sep 2026",
    trackingNumber: "AMZN-IN-889102",
    carrier: "Amazon Transportation Services",
    subtotal: 1899,
    shipping: 0,
    discount: 200,
    total: 1699,
    items: [
      {
        name: "Levi's Men's 511 Slim Fit Stretch Jeans",
        image: "https://images.unsplash.com/photo-1542272604-780c96856592?auto=format&fit=crop&w=800&q=80",
        retailer: "Amazon India",
        price: 1699,
        quantity: 1,
        variantName: "Size 32 Dark Blue",
      },
    ],
  },
  {
    id: "ord_10285",
    orderNumber: "PP-654992",
    date: "15 Sep 2026",
    retailer: "Nykaa",
    status: "delivered",
    estimatedDelivery: "Delivered on 17 Sep 2026",
    trackingNumber: "NYK-EXP-44910",
    carrier: "BlueDart Express",
    subtotal: 549,
    shipping: 0,
    discount: 50,
    total: 499,
    items: [
      {
        name: "Maybelline Fit Me Matte+Poreless Liquid Foundation",
        image: "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80",
        retailer: "Nykaa",
        price: 499,
        quantity: 1,
        variantName: "128 Warm Nude 30ml",
      },
    ],
  },
];

const OrderContext = createContext<OrderContextType | undefined>(undefined);
const ORDERS_STORAGE_KEY = "pricepilot_orders_v1";

export function OrderProvider({ children }: { children: React.ReactNode }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(ORDERS_STORAGE_KEY);
      if (saved) {
        setOrders(JSON.parse(saved));
      } else {
        setOrders(INITIAL_ORDERS);
      }
    } catch {
      setOrders(INITIAL_ORDERS);
    }
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) {
      localStorage.setItem(ORDERS_STORAGE_KEY, JSON.stringify(orders));
    }
  }, [orders, isLoaded]);

  const placeOrder = (cartItems: CartItem[], retailer: string, total: number): Order => {
    const orderNum = `PP-${Math.floor(100000 + Math.random() * 900000)}`;
    const newOrder: Order = {
      id: `ord_${Date.now()}`,
      orderNumber: orderNum,
      date: new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }),
      retailer: retailer || "PricePilot Universal Hub",
      status: "confirmed",
      estimatedDelivery: "Delivery in 2 - 3 Days",
      trackingNumber: `EXP-${Math.random().toString(36).substring(2, 10).toUpperCase()}`,
      carrier: `${retailer} Priority Express`,
      subtotal: total,
      shipping: 0,
      discount: 0,
      total,
      items: cartItems.map((item) => ({
        name: item.name,
        image: item.image,
        retailer: item.retailer,
        price: item.price,
        quantity: item.quantity,
      })),
    };

    setOrders((prev) => [newOrder, ...prev]);
    return newOrder;
  };

  const claimPriceDropRefund = (orderId: string, refundAmount: number) => {
    setOrders((prev) =>
      prev.map((ord) =>
        ord.id === orderId
          ? {
              ...ord,
              priceDropRefundClaimed: true,
              priceDropRefundAmount: refundAmount,
            }
          : ord
      )
    );
  };

  return (
    <OrderContext.Provider value={{ orders, placeOrder, claimPriceDropRefund }}>
      {children}
    </OrderContext.Provider>
  );
}

export function useOrders() {
  const context = useContext(OrderContext);
  if (!context) {
    throw new Error("useOrders must be used within an OrderProvider");
  }
  return context;
}

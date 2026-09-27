"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export interface UserAddress {
  id: string;
  label: string;
  name: string;
  phone: string;
  street: string;
  city: string;
  state: string;
  pincode: string;
  isDefault: boolean;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  membershipTier: "Standard" | "PricePilot Pro" | "VIP SuperSaver";
  totalSaved: number;
  addresses: UserAddress[];
  priceAlertsCount: number;
  activeOrdersCount: number;
  isAuthenticated: boolean;
}

interface AuthContextType {
  user: UserProfile;
  login: (email: string, name?: string) => void;
  logout: () => void;
  updateProfile: (updated: Partial<UserProfile>) => void;
}

const DEFAULT_USER: UserProfile = {
  id: "usr_991823",
  name: "Rahul Sharma",
  email: "rahul.sharma@example.com",
  phone: "+91 98765 43210",
  avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=200&q=80",
  membershipTier: "PricePilot Pro",
  totalSaved: 14850,
  priceAlertsCount: 4,
  activeOrdersCount: 2,
  isAuthenticated: true,
  addresses: [
    {
      id: "addr_1",
      label: "Home",
      name: "Rahul Sharma",
      phone: "+91 98765 43210",
      street: "Flat 402, Green Glen Heights, Bellandur",
      city: "Bengaluru",
      state: "Karnataka",
      pincode: "560103",
      isDefault: true,
    },
    {
      id: "addr_2",
      label: "Office",
      name: "Rahul Sharma (PricePilot)",
      phone: "+91 98765 43210",
      street: "Level 6, Tech Park, Outer Ring Road",
      city: "Bengaluru",
      state: "Karnataka",
      pincode: "560100",
      isDefault: false,
    },
  ],
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = "pricepilot_user_v1";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile>(DEFAULT_USER);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(AUTH_STORAGE_KEY);
      if (saved) {
        setUser(JSON.parse(saved));
      }
    } catch {
      // fallback to DEFAULT_USER
    }
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    }
  }, [user, isLoaded]);

  const login = (email: string, name = "Shopping Explorer") => {
    setUser((prev) => ({
      ...prev,
      email,
      name,
      isAuthenticated: true,
    }));
  };

  const logout = () => {
    setUser((prev) => ({
      ...prev,
      isAuthenticated: false,
    }));
  };

  const updateProfile = (updated: Partial<UserProfile>) => {
    setUser((prev) => ({ ...prev, ...updated }));
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

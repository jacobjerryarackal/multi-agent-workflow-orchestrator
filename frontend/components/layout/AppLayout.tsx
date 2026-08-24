"use client";

import React, { useState, useCallback } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleCloseMobile = useCallback(() => {
    setIsMobileOpen(false);
  }, []);

  const handleToggleMobile = useCallback(() => {
    setIsMobileOpen((prev) => !prev);
  }, []);

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans">
      <Sidebar
        isMobileOpen={isMobileOpen}
        onCloseMobile={handleCloseMobile}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Header onToggleMobileMenu={handleToggleMobile} />
        <main className="flex-1 p-4 sm:p-6 overflow-y-auto max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

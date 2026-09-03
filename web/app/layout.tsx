import { Assistant } from "next/font/google";
import { Suspense } from "react";
import { AppHeader } from "@/components/AppHeader";
import "./globals.css";

const assistant = Assistant({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  display: "swap",
});

export const metadata = {
  title: "Myntra · Wishlist insights",
  description: "Why people save fashion items but don’t buy — within a month and overall",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={assistant.className}>
        <Suspense fallback={<div className="h-[108px] bg-white shadow-card" />}>
          <AppHeader />
        </Suspense>
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
        <footer className="border-t border-myntra-line bg-white py-6 text-center text-xs text-myntra-muted">
          For Myntra teams · Built from public shopper comments
        </footer>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Figtree } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Customer Intelligence Platform",
  description: "Churn, CLV, segmentation, and retention analytics",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${figtree.variable} h-full antialiased`}>
      <body className="min-h-full bg-paper text-ink">
        <Nav />
        <div className="lg:pl-60">
          <main className="mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-8 sm:py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

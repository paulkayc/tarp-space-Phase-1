import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Tarp-Space",
  description: "Local marketplace powered by AI agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-base text-primary antialiased">
        <Navbar />
        <div className="h-full pt-14">{children}</div>
      </body>
    </html>
  );
}

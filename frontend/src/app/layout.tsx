import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareOS Health",
  description: "A coordinated healthcare assistant",
  manifest: "/manifest.json",
  icons: {
    icon: "/careos-icon.svg",
    apple: "/careos-icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

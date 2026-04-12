import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Deep Vision by DNS",
  description: "Plataforma de videoanalitica profesional",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className="bg-background text-text-primary antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}

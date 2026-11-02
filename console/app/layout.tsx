import type { Metadata } from "next";
import "../styles/globals.css";
import "../styles/glass.css";
import { ThemeProvider } from "../providers/ThemeProvider";
import { QueryProvider } from "../providers/QueryProvider";
import { I18nProvider } from "../providers/I18nProvider";
import { Toaster } from "sonner";
import { AuthProvider } from "../providers/AuthProvider";
import TouchProvider from "./(providers)/TouchProvider";

export const metadata: Metadata = {
  title: "OMERTA OS Console",
  description: "Operator console for the OMERTA OS platform",
  icons: {
    icon: "/brand/omertaos-logo.png",
    apple: "/brand/omertaos-logo.png",
  },
};

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body className="min-h-screen text-white antialiased">
        <I18nProvider>
          <ThemeProvider>
            <AuthProvider>
              <QueryProvider>
                <TouchProvider>
                  <>
                    {children}
                    <Toaster richColors position="bottom-right" closeButton />
                  </>
                </TouchProvider>
              </QueryProvider>
            </AuthProvider>
          </ThemeProvider>
        </I18nProvider>
      </body>
    </html>
  );
}

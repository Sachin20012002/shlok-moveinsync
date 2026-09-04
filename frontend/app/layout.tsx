import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SHLOK | Mobility Control Room",
  description: "Agentic operations intelligence for enterprise mobility",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SHLOK | MoveInSync Hackathon",
  description: "SHLOK MoveInSync infrastructure smoke test",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

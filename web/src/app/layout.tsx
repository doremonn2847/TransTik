import type { Metadata } from "next";
import { Geist, Geist_Mono, Newsreader } from "next/font/google";
import { Nav, Providers } from "@/components/ui";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin", "latin-ext"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Serif for transcript text: long passages read better, and it marks them as documents.
const newsreader = Newsreader({ variable: "--font-newsreader", subsets: ["latin", "latin-ext", "vietnamese"], style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: { default: "TransTik", template: "%s · TransTik" },
  description: "Transcripts of TikTok, Instagram Reels and YouTube Shorts, in a private library.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${newsreader.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>
          <Nav />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {title:"Kakakin — Every voice, further",description:"Reach your community. Grow through connection. A consent-first campaign workspace.",icons:{icon:"/favicon.svg"},manifest:"/manifest.json"};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="en"><body>{children}</body></html>}

import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AlgoForge Dashboard — Trading Monitor',
  description: 'Real-time monitoring dashboard for the AlgoForge quantitative trading system. Live P&L, signal health, regime detection, and kill switch.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

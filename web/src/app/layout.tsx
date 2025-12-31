import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ContextHarness',
  description: 'Web interface for managing ContextHarness sessions and agents',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 dark:bg-slate-900">
        {children}
      </body>
    </html>
  );
}

import "./globals.css";

export const metadata = {
  title: "Codebase Explainer",
  description: "UI for ingesting repositories and exploring architecture with grounded answers.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

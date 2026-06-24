"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";

interface NavLink {
  href: string;
  label: string;
}

const superuserLinks: NavLink[] = [
  { href: "/sessions", label: "Sessions" },
  { href: "/audit", label: "Audit" },
  { href: "/users", label: "Users" },
  { href: "/dashboard", label: "Dashboard" },
];

const managerLinks: NavLink[] = [
  { href: "/sessions", label: "Sessions" },
  { href: "/audit", label: "Audit" },
  { href: "/dashboard", label: "Dashboard" },
];

const defaultLinks: NavLink[] = [
  { href: "/register", label: "Register" },
  { href: "/dashboard", label: "Dashboard" },
];

function getLinksForRole(role: string | undefined): NavLink[] {
  switch (role) {
    case "superuser":
      return superuserLinks;
    case "manager":
      return managerLinks;
    default:
      return defaultLinks;
  }
}

export function Nav() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  const links = isAuthenticated ? getLinksForRole(user?.global_role) : [];

  const closeMobile = useCallback(() => {
    setMobileOpen(false);
    toggleRef.current?.focus();
  }, []);

  const handleToggle = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape" && mobileOpen) {
        closeMobile();
      }
    },
    [mobileOpen, closeMobile],
  );

  return (
    <nav aria-label="Main navigation" className="border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="text-lg font-semibold text-foreground">
          Carpool Coordinator
        </Link>

        {/* Desktop links */}
        <ul className="hidden items-center gap-1 md:flex">
          {links.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={pathname === link.href ? "page" : undefined}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-3 md:flex">
          {isAuthenticated ? (
            <>
              <span className="text-sm text-muted-foreground">{user?.email}</span>
              <button
                type="button"
                onClick={logout}
                className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Log out
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
            >
              Sign in
            </Link>
          )}
        </div>

        {/* Mobile toggle */}
        <button
          ref={toggleRef}
          type="button"
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav"
          onClick={handleToggle}
          className="rounded-md p-2 text-muted-foreground hover:bg-muted md:hidden"
        >
          <span className="sr-only">{mobileOpen ? "Close menu" : "Open menu"}</span>
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
              />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile panel */}
      {mobileOpen && (
        <div
          id="mobile-nav"
          className="border-t border-border px-4 pb-4 md:hidden"
          onKeyDown={handleKeyDown}
        >
          <ul className="flex flex-col gap-1 pt-3">
            {links.map((link, i) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  aria-current={pathname === link.href ? "page" : undefined}
                  onClick={closeMobile}
                  autoFocus={i === 0}
                  className={`block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    pathname === link.href
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-3 border-t border-border pt-3">
            {isAuthenticated ? (
              <button
                type="button"
                onClick={() => {
                  logout();
                  closeMobile();
                }}
                className="w-full rounded-md border border-border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Log out
              </button>
            ) : (
              <Link
                href="/login"
                onClick={closeMobile}
                className="block w-full rounded-md bg-primary px-3 py-2 text-center text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

import { NextRequest, NextResponse } from 'next/server';
import { getSessionCookie } from 'better-auth/cookies';

export function proxy(request: NextRequest) {
  const session = getSessionCookie(request);

  if (!session) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('callbackUrl', request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Protect all routes except:
     * - /login
     * - /api/auth/** (better-auth endpoints)
     * - Next.js internals and static files
     */
    '/((?!login|signup|api/auth|_next/static|_next/image|favicon.ico|icon.*|apple-icon.*|placeholder.*).*)',
  ],
};

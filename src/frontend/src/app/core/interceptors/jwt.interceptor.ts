import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  // Skip auth header for refresh/login/logout endpoints
  const isAuthEndpoint =
    req.url.includes('/auth/refresh') ||
    req.url.includes('/auth/login') ||
    req.url.includes('/auth/logout');

  let cloned = req;
  if (!isAuthEndpoint) {
    const token = auth.getToken();
    if (token) {
      cloned = req.clone({
        setHeaders: { Authorization: `Bearer ${token}` },
      });
    }
  }

  return next(cloned).pipe(
    catchError((error: HttpErrorResponse) => {
      // Only attempt refresh on 401 and non-auth endpoints
      if (error.status === 401 && !isAuthEndpoint) {
        return from(auth.refreshToken()).pipe(
          switchMap((newToken) => {
            if (newToken) {
              const retried = req.clone({
                setHeaders: { Authorization: `Bearer ${newToken}` },
              });
              return next(retried);
            }
            auth.logout();
            return throwError(() => error);
          }),
          catchError(() => {
            auth.logout();
            return throwError(() => error);
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};

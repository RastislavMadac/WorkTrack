import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (req, next) => {

    // 1. Ignorujeme login endpoint (aby sme neposielali starý token a nerobili cykly)
    if (req.url.includes('api-token-auth')) {
        return next(req);
    }

    // 2. ZMENA: Čítame token zo sessionStorage
    const token = sessionStorage.getItem('token');

    if (token) {
        const cloned = req.clone({
            setHeaders: {
                Authorization: `Token ${token}`
            }
        });
        return next(cloned);
    }

    return next(req);
};
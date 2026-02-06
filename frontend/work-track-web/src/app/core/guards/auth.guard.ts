import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route, state) => {
    const authService = inject(AuthService); // Použijeme tvoju service
    const router = inject(Router);

    if (authService.isAuthenticated()) {
        return true; // Má token -> Pustíme ho ďalej
    } else {
        // Nemá token -> Presmerujeme na login
        router.createUrlTree(['/login']);
        return false;
    }
};
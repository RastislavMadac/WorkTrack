import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { NotificationService } from '../services/notification.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
    const notify = inject(NotificationService);

    return next(req).pipe(
        catchError((error: HttpErrorResponse) => {
            console.log('🛑 Interceptor zachytil chybu:', error.status); // DEBUG

            // 1. Chyba 400 (Zlé heslo)
            if (error.status === 400) {
                // Nerobíme nič, necháme to na komponent
                console.log('➡️ Posúvam 400 do komponentu');
            }
            // 2. Ostatné chyby (Server, Sieť)
            else if (error.status >= 500) {
                notify.showError('Chyba servera.');
            }
            else if (error.status === 0) {
                notify.showError('Nepodarilo sa spojiť so serverom.');
            }

            // ⚠️ TOTO JE NAJDÔLEŽITEJŠÍ RIADOK ⚠️
            // Musíme chybu "hodiť" ďalej, inak sa error() v komponente nespustí!
            return throwError(() => error);
        })
    );
};
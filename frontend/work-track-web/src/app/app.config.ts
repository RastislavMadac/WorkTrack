import { ApplicationConfig, LOCALE_ID } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './core/interceptors/auth.interceptor'
import { errorInterceptor } from './core/interceptors/error.interceptor'
import localeSk from '@angular/common/locales/sk';
import { registerLocaleData } from '@angular/common';

registerLocaleData(localeSk);
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor, errorInterceptor])),
    { provide: LOCALE_ID, useValue: 'sk' }

  ]

};


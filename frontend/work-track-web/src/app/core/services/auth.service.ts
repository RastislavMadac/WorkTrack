import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs'; // 👈 Pridaj 'of' do importu
import { switchMap, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CurrentUser, User } from '../../shared/models/user.model';

export interface AuthResponse {
    token: string;
}

@Injectable({
    providedIn: 'root'
})
export class AuthService {
    private apiUrl = environment.apiUrl;
    private http = inject(HttpClient);
    private router = inject(Router);

    login(credentials: { username: string, password: string }): Observable<CurrentUser> {
        return this.http.post<any>(`${this.apiUrl}api-token-auth/`, credentials)
            .pipe(
                tap(response => {
                    sessionStorage.setItem('token', response.token);
                }),
                switchMap(() => {
                    return this.http.get<CurrentUser>(`${this.apiUrl}current-user/`);
                }),
                tap(user => {
                    sessionStorage.setItem('username', user.username);
                    sessionStorage.setItem('first_name', user.first_name || '');
                    sessionStorage.setItem('last_name', user.last_name || '');
                    sessionStorage.setItem('user_id', user.id.toString());
                    sessionStorage.setItem('role', user.role); // Predpokladáme, že backend vracia 'admin', 'manager', 'worker'
                })
            );
    }

    getRole(): string {
        return sessionStorage.getItem('role') || 'worker';
    }

    logout(): void {
        sessionStorage.clear();
        this.router.navigate(['/login']);
    }

    isAdmin(): boolean {
        return this.getRole() === 'admin';
    }

    // Manažér alebo Admin majú rozšírené práva
    isManager(): boolean {
        const role = this.getRole();
        return role === 'manager' || role === 'admin';
    }

    // Má prístup do plánovača? (Aj worker má prístup, ale obmedzený)
    hasPlannerAccess(): boolean {
        // Všetci prihlásení majú prístup, ale uvidia iné dáta
        return this.isAuthenticated();
    }

    getFullName(): string {
        const firstName = sessionStorage.getItem('first_name');
        const lastName = sessionStorage.getItem('last_name');
        const username = sessionStorage.getItem('username');

        if (firstName || lastName) {
            return `${firstName || ''} ${lastName || ''}`.trim();
        }
        return username || 'Neznámy používateľ';
    }

    isAuthenticated(): boolean {
        return !!sessionStorage.getItem('token');
    }

    getActiveUsers(): Observable<User[]> {
        return this.http.get<User[]>(`${this.apiUrl}active-users/`);
    }

    // ✅ NOVÁ METÓDA: Vráti aktuálneho používateľa ako pole (pre Worker pohľad)
    getCurrentUserAsList(): Observable<User[]> {
        const user: User = {
            id: Number(sessionStorage.getItem('user_id')),
            username: sessionStorage.getItem('username') || '',
            first_name: sessionStorage.getItem('first_name') || '',
            last_name: sessionStorage.getItem('last_name') || '',

            role: this.getRole() as any // Pretypovanie ak treba
            ,
            personal_number: ''
        };
        return of([user]);
    }
}
import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export interface Notification {
    message: string;
    type: 'success' | 'error' | 'info';
}

@Injectable({
    providedIn: 'root'
})
export class NotificationService {
    // Subject je ako "vysielač". Komponenty ho budú počúvať.
    private notificationSubject = new Subject<Notification | null>();

    // Toto budeme odoberať v komponente
    notification$ = this.notificationSubject.asObservable();

    showSuccess(message: string) {
        this.notificationSubject.next({ message, type: 'success' });
    }

    showError(message: string) {
        this.notificationSubject.next({ message, type: 'error' });
    }

    showInfo(message: string) {
        this.notificationSubject.next({ message, type: 'info' });
    }

    clear() {
        this.notificationSubject.next(null);
    }
}
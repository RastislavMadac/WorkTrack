import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ChangeReason } from '../../shared/models/changeReason.model';

@Injectable({
    providedIn: 'root'
})
export class ChangeReasonService {
    private http = inject(HttpClient);
    private apiUrl = `${environment.apiUrl}changereason/`;

    getReasons(): Observable<ChangeReason[]> {
        return this.http.get<ChangeReason[]>(this.apiUrl);
    }
}
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TypeShift } from '../../shared/models/typeShift.model';



@Injectable({
    providedIn: 'root'
})


export class TypeShiftService {

    private http = inject(HttpClient);

    private apiUrl = environment.apiUrl;
    getShiftTypes(): Observable<TypeShift[]> {
        return this.http.get<TypeShift[]>(`${environment.apiUrl}typeshift/`);
        // Uisti sa, že máš tento endpoint v Django urls.py
    }
}
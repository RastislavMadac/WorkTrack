import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AttendancePayload } from '../../shared/models/attendance.model';

@Injectable({
    providedIn: 'root'
})
export class AttendanceService {
    private http = inject(HttpClient);
    private apiUrl = `${environment.apiUrl}attendance/`;

    getAttendances(year?: number, month?: number): Observable<any[]> {
        let params = new HttpParams();
        if (year) params = params.set('year', year.toString());
        if (month) params = params.set('month', month.toString());
        return this.http.get<any[]>(this.apiUrl, { params });
    }

    createAttendance(payload: AttendancePayload): Observable<any> {
        return this.http.post<any>(this.apiUrl, payload);
    }

    updateAttendance(id: number, payload: Partial<AttendancePayload>): Observable<any> {
        return this.http.patch<any>(`${this.apiUrl}${id}/`, payload);
    }

    downloadPdf(userId: number, year: number, month: number) {
        const url = `${this.apiUrl}export-attendance-pdf/?user_id=${userId}&year=${year}&month=${month}`;
        window.open(url, '_blank');
    }
}
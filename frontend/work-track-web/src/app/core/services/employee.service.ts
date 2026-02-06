import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User } from '../../shared/models/user.model';
import { EmployeePayload } from '../../shared/models/employee.model';



@Injectable({
    providedIn: 'root'
})
export class EmployeeService {
    private apiUrl = `${environment.apiUrl}employees/`;
    private http = inject(HttpClient);

    getEmployees(): Observable<EmployeePayload[]> {
        return this.http.get<EmployeePayload[]>(this.apiUrl);
    }

    getEmployee(id: number): Observable<EmployeePayload> {
        return this.http.get<EmployeePayload>(`${this.apiUrl}${id}/`);
    }

    createEmployee(employee: EmployeePayload): Observable<EmployeePayload> {
        return this.http.post<EmployeePayload>(this.apiUrl, employee);
    }

    updateEmployee(id: number, employee: Partial<EmployeePayload>): Observable<EmployeePayload> {
        return this.http.patch<EmployeePayload>(`${this.apiUrl}${id}/`, employee);
    }

    deleteEmployee(id: number): Observable<void> {
        return this.http.delete<void>(`${this.apiUrl}${id}/`);
    }
}



import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { MonthlySummary, PlannedShift } from '../../shared/models/plannedShift.model';
import { YearlyReportResponse } from '../../shared/models/yearReport_model';



@Injectable({
    providedIn: 'root'
})
export class PlannerService {
    // Django router má adresu: /plannedshift/
    private apiUrl = `${environment.apiUrl}plannedshift/`;
    private apiUrlReport = `${environment.apiUrl}`;
    private http = inject(HttpClient);


    getShifts(year: number, month: number): Observable<PlannedShift[]> {
        const params = new HttpParams()
            .set('year', year.toString())
            .set('month', month.toString())
            .set('hidden', 'false'); // Chceme len tie, čo nie sú zmazané

        return this.http.get<PlannedShift[]>(this.apiUrl, { params });
    }

    /**
     * Vytvorí novú zmenu.
     * Pozor: Backend kontroluje prekrývanie (overlap) a vráti 400 ak je konflikt.
     */
    createShift(shift: PlannedShift): Observable<PlannedShift> {
        return this.http.post<PlannedShift>(this.apiUrl, shift);
    }

    /**
     * Upraví existujúcu zmenu.
     * Používame PATCH, lebo meníme len časť dát.
     */
    updateShift(id: number, shift: Partial<PlannedShift>): Observable<PlannedShift> {
        return this.http.patch<PlannedShift>(`${this.apiUrl}${id}/`, shift);
    }

    /**
     * Vymaže zmenu.
     * Backend má pole 'hidden', ale DELETE endpoint zvyčajne robí hard-delete
     * alebo backend sám nastaví hidden=True. Skúsime klasický delete.
     */
    deleteShift(id: number): Observable<void> {
        return this.http.delete<void>(`${this.apiUrl}${id}/`);
    }

    getPreviousMonthBalance(year: number, month: number): Observable<MonthlySummary[]> {
        // Toto je len príklad, ideálne by to mal vrátiť backend
        // Ak nemáš hromadný endpoint, musíme to zatiaľ nechať prázdne alebo volať pre každého usera
        return this.http.get<MonthlySummary[]>(`${this.apiUrl}balances/`, {
            params: { year: year.toString(), month: month.toString() }
        });
    }
    getWorkingFund(year: number, month: number): Observable<any> {
        // Endpoint definovaný v urls.py: working_fund/<int:year>/<int:month>/
        return this.http.get<any>(`${environment.apiUrl}working_fund/${year}/${month}/`);
    }

    getBalances(year: number, month: number): Observable<{ [key: number]: number }> {
        return this.http.get<{ [key: number]: number }>(`${environment.apiUrl}balances/${year}/${month}/`);
    }
    getMonthlyStats(year: number, month: number): Observable<MonthlySummary[]> {
        const params = new HttpParams()
            .set('year', year.toString())
            .set('month', month.toString());

        // Tu predpokladám endpoint 'stats'. Ak sa volá inak, prepíšte to.
        return this.http.get<MonthlySummary[]>(`${this.apiUrl}stats/`, { params });
    }

    getYearlyReport(year: number): Observable<YearlyReportResponse> {
        const params = new HttpParams().set('year', year.toString());
        return this.http.get<YearlyReportResponse>(`${this.apiUrlReport}reports/yearly-overview/`, { params });
    }

    // Pridaj do triedy PlannerService

    copyMonthlyPlan(sourceYear: number, sourceMonth: number, targetYear: number, targetMonth: number): Observable<any> {
        const body = {
            source_year: sourceYear,
            source_month: sourceMonth,
            target_year: targetYear,
            target_month: targetMonth
        };
        return this.http.post(`${this.apiUrl}copy/`, body);
    }
    requestExchange(shiftId: number, targetUserId: number, reasonId: number): Observable<any> {
        return this.http.post(`${this.apiUrl}${shiftId}/request-exchange/`, {
            target_user_id: targetUserId,
            change_reason: reasonId
        });
    }

    decideExchange(shiftId: number, status: 'approved' | 'rejected', note: string): Observable<any> {
        return this.http.post(`${this.apiUrl}${shiftId}/decide-exchange/`, {
            status,
            manager_note: note
        });
    }
}



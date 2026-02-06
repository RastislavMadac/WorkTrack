import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Observable, forkJoin } from 'rxjs';

import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { PlannedShift, MonthlySummary } from '../../shared/models/plannedShift.model';
import { PlannerService } from '../../core/services/plannedShift.service';
import { User } from '../../shared/models/user.model';
import { TypeShift } from '../../shared/models/typeShift.model';
import { TypeShiftService } from '../../core/services/tapeShift.service';
import { HeaderComponent } from '../../core/components/header/header';
import { ChangeReason } from '../../shared/models/changeReason.model';
import { ChangeReasonService } from '../../core/services/changeReason.service';
import { YearlyReportResponse } from '../../shared/models/yearReport_model';

interface CalendarDay {
  date: Date;
  dayNum: number;
  dayName: string;
  isWeekend: boolean;
  isHoliday: boolean;
}

interface EmployeeRow {
  user_id: number;
  fullName: string;
  shifts: { [day: number]: PlannedShift | null };
  stats: {
    fund: number;
    worked: number;
    diff: number;
    night: number;
    weekend: number;
    holiday: number;
    prevBalance: number;
    total: number;
  };
}

@Component({
  selector: 'app-planner',
  standalone: true,
  imports: [CommonModule, FormsModule, HeaderComponent],
  templateUrl: './planner.html',
  styleUrls: ['./planner.scss']
})
export class PlannerComponent implements OnInit {
  changeReasons: ChangeReason[] = [];
  isModalOpen = false;
  shiftTypes: TypeShift[] = [];
  currentDate = new Date();
  daysInMonth: CalendarDay[] = [];
  monthlyFund: number = 0;

  employeeRows: EmployeeRow[] = [];
  isLoading = false;
  isManager = false;

  showPrevMonthPreview = false;
  prevMonthRows: EmployeeRow[] = [];

  // Editácia
  selectedShift: Partial<PlannedShift> = {};
  selectedRowUser: EmployeeRow | null = null;
  selectedDay: CalendarDay | null = null;
  canEditTime = false;

  // Ročný report
  yearlyReport: YearlyReportResponse | null = null;
  isYearlyReportLoading = false;
  monthNames = [
    'Január', 'Február', 'Marec', 'Apríl', 'Máj', 'Jún',
    'Júl', 'August', 'September', 'Október', 'November', 'December'
  ];
  monthsIndices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];


  activeColleagues: User[] = [];

  // UI stav pre modal
  isExchangeMode = false;
  selectedExchangeUser: number | null = null;
  currentUserId: number | null = null;
  // Injekcie
  private plannerService = inject(PlannerService);
  private authService = inject(AuthService);
  private notify = inject(NotificationService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);
  private changeReasonService = inject(ChangeReasonService);
  private typeShiftService = inject(TypeShiftService);

  ngOnInit() {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    this.currentUserId = Number(sessionStorage.getItem('user_id'));
    this.isManager = this.authService.isManager();

    // Spustíme načítanie dát
    this.loadMonthData();

    // Načítame číselníky
    this.typeShiftService.getShiftTypes().subscribe(types => {
      this.shiftTypes = types;
    });
    this.changeReasonService.getReasons().subscribe(reasons => {
      this.changeReasons = reasons;
    });
    // Načítaj zoznam kolegov pre dropdown
    this.authService.getActiveUsers().subscribe(users => {

      this.activeColleagues = users;
    });


  }
  get exchangeCandidates(): any[] { // alebo User[] ak máš importovaný interface
    if (!this.selectedShift || !this.selectedShift.user) {
      return [];
    }
    // Vráti všetkých kolegov OKREM toho, ktorému patrí táto smena
    return this.activeColleagues.filter(u => u.id !== this.selectedShift.user);
  }

  get canRequestExchange(): boolean {
    // 1. Smena musí existovať
    if (!this.selectedShift || !this.selectedShift.id) {
      return false;
    }

    // 2. Ak je smena už zamietnutá, nedá sa riešiť (voliteľné)
    if (this.selectedShift.approval_status === 'rejected') {
      // Tu záleží na logike, či chcete povoliť opravu zamietnutej. 
      // Ak áno, tento if vymažte.
    }

    // 3. Ak je používateľ Manažér alebo Admin -> Môže meniť všetko
    if (this.isManager) {
      return true;
    }

    // 4. Ak je Worker -> Môže meniť IBA SVOJU smenu
    return this.selectedShift.user === this.currentUserId;
  }
  get canEditDetails(): boolean {
    return this.isManager;
  }

  loadMonthData() {
    this.isLoading = true;
    this.cdr.detectChanges();

    const year = this.currentDate.getFullYear();
    const month = this.currentDate.getMonth() + 1;

    // 1. Vygenerujeme kalendár
    this.generateCalendarDays(year, month);

    // 2. Users Request
    let usersRequest$: Observable<User[]>;
    if (this.isManager) {
      usersRequest$ = this.authService.getActiveUsers();
    } else {
      usersRequest$ = this.authService.getCurrentUserAsList();
    }

    // 3. Fond + Sviatky
    this.plannerService.getWorkingFund(year, month).subscribe({
      next: (fundData) => {
        this.monthlyFund = fundData.working_fund_hours;

        // Sviatky
        const holidays = fundData.holidays || [];
        this.daysInMonth = this.daysInMonth.map(day => ({
          ...day,
          isHoliday: holidays.includes(day.dayNum)
        }));

        this.fetchUsersAndShifts(year, month, usersRequest$);
        this.loadYearlyReport(); // Načítaj aj spodnú tabuľku
      },
      error: (err) => {
        console.error('Fallback fond', err);
        // Fallback výpočet
        const workingDays = this.daysInMonth.filter(d => !d.isWeekend).length;
        this.monthlyFund = workingDays * 7.5;

        this.fetchUsersAndShifts(year, month, usersRequest$);
        this.loadYearlyReport();
      }
    });
  }

  fetchUsersAndShifts(year: number, month: number, usersRequest$: Observable<User[]>) {
    usersRequest$.subscribe({
      next: (users) => {
        forkJoin({
          shifts: this.plannerService.getShifts(year, month),
          stats: this.plannerService.getMonthlyStats(year, month)
        }).subscribe({
          next: ({ shifts, stats }) => {

            // Vytvoríme štruktúru riadkov
            this.employeeRows = users.map(user => {
              const userStat = stats.find(s => s.user_id === user.id) || {
                user_id: user.id, prevBalance: 0, fund: this.monthlyFund, worked: 0, diff: 0, total: 0, night: 0, weekend: 0, holiday: 0
              };

              return {
                user_id: user.id,
                fullName: `${user.first_name} ${user.last_name}`.trim() || user.username,
                shifts: {},
                stats: {
                  fund: userStat.fund,
                  worked: userStat.worked,
                  diff: userStat.diff,
                  night: userStat.night,
                  weekend: userStat.weekend,
                  holiday: userStat.holiday,
                  prevBalance: userStat.prevBalance,
                  total: userStat.total
                }
              };
            });

            // Rozhádžeme smeny
            this.distributeShiftsToRows(shifts);

            this.isLoading = false;
            this.cdr.detectChanges(); // Aktualizuj view
          },
          error: (err) => {
            console.error(err);
            this.isLoading = false;
            this.notify.showError('Chyba pri načítaní dát.');
            this.cdr.detectChanges();
          }
        });
      },
      error: () => {
        this.isLoading = false;
        this.notify.showError('Chyba pri načítaní zamestnancov');
        this.cdr.detectChanges();
      }
    });
  }

  distributeShiftsToRows(shifts: PlannedShift[]) {
    shifts.forEach(shift => {
      // ⚠️ OPRAVA: Bezpečné parsovanie dňa (ignoruje časové pásma)
      // Predpokladáme formát "YYYY-MM-DD"
      const parts = shift.date.split('-');
      const day = parseInt(parts[2], 10); // Vezmeme deň priamo zo stringu

      const row = this.employeeRows.find(r => r.user_id === shift.user);
      if (row) {
        row.shifts[day] = shift;
      }
    });
  }

  // --- KALENDÁR LOGIKA ---
  generateCalendarDays(year: number, month: number) {
    const daysInMonth = new Date(year, month, 0).getDate();
    this.daysInMonth = [];

    for (let i = 1; i <= daysInMonth; i++) {
      const date = new Date(year, month - 1, i);
      const dayOfWeek = date.getDay();

      this.daysInMonth.push({
        dayNum: i,
        dayName: this.getDayName(dayOfWeek),
        isWeekend: dayOfWeek === 0 || dayOfWeek === 6,
        isHoliday: false,
        date: date
      });
    }
  }

  getDayName(dayIndex: number): string {
    const days = ['Ne', 'Po', 'Ut', 'St', 'Št', 'Pi', 'So'];
    return days[dayIndex];
  }

  changeMonth(delta: number) {
    this.currentDate = new Date(this.currentDate.setMonth(this.currentDate.getMonth() + delta));
    this.loadMonthData();
  }

  prevMonth() { this.changeMonth(-1); }
  nextMonth() { this.changeMonth(1); }

  togglePrevMonthPreview() {
    this.showPrevMonthPreview = !this.showPrevMonthPreview;
    if (this.showPrevMonthPreview && this.prevMonthRows.length === 0) {
      this.notify.showInfo('Náhľad minulého mesiaca zatiaľ nie je implementovaný.');
    }
  }

  savePlan() {
    if (this.isManager) {
      this.notify.showSuccess('Plán bol uložený (Simulácia)');
    }
  }

  // --- ROČNÝ REPORT LOGIKA ---
  loadYearlyReport() {
    this.isYearlyReportLoading = true;
    const year = this.currentDate.getFullYear();

    this.plannerService.getYearlyReport(year).subscribe({
      next: (data) => {
        this.yearlyReport = data;
        this.isYearlyReportLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error(err);
        // this.notify.showError('Nepodarilo sa načítať ročný prehľad');
        this.isYearlyReportLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  getHolidayHours(holiday: any, userId: number): string | number {
    const record = holiday.records.find((r: any) => r.user_id === userId);
    return record && record.hours > 0 ? record.hours : '-';
  }

  openShiftEdit(row: EmployeeRow, day: CalendarDay) {
    // 1. Reset stavu výmeny
    this.isExchangeMode = false;
    this.selectedExchangeUser = null;

    // 2. Získame existujúcu smenu (ak je)
    const existingShift = row.shifts[day.dayNum];

    // --- 3. KONTROLA OPRÁVNENÍ ---

    // Ak NIE SOM manažér...
    if (!this.isManager) {
      // ... a klikol som na cudzí riadok -> KONČÍM
      if (row.user_id !== this.currentUserId) {
        return;
      }
      // ... a smena neexistuje (chcem vytvoriť novú) -> KONČÍM (Zamestnanec nesmie vytvárať)
      if (!existingShift) {
        return;
      }
    }
    // -----------------------------

    this.selectedRowUser = row; // alebo { id: row.id, fullName: row.fullName } podľa vášho modelu
    this.selectedDay = day;

    if (existingShift) {
      // Existujúca smena - skopírujeme dáta
      this.selectedShift = { ...existingShift };
    } else {
      // Nová smena (sem sa dostane len Manažér vďaka podmienke vyššie)
      this.selectedShift = {
        user: row.user_id, // alebo row.user_id, skontrolujte si model
        date: this.getLocalDateString(day.date),
        type_shift: undefined, // Tu pozor, 'undefined' môže robiť problém v selecte, lepšie je null
        transferred: false,
        is_changed: false,
        hidden: false
      };
    }

    // 4. Otvoríme modal
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
    this.selectedShift = {};
  }

  // Dropdown zmena
  onShiftTypeChange() {
    const typeId = this.selectedShift.type_shift;
    const type = this.shiftTypes.find(t => t.id == typeId);

    if (type) {
      this.canEditTime = type.allow_variable_time;

      if (this.canEditTime) {
        // Variabilná - vymažeme časy, ak tam nejaké boli
        // (voliteľné, možno ich chcete nechať)
      } else {
        // Fixná - nastavíme časy
        this.selectedShift.custom_start = type.start_time ? type.start_time.substring(0, 5) : undefined;
        this.selectedShift.custom_end = type.end_time ? type.end_time.substring(0, 5) : undefined;
      }
    } else {
      this.canEditTime = false;
      this.selectedShift.custom_start = undefined;
      this.selectedShift.custom_end = undefined;
    }

    this.parseTimeToSelects();
    this.calculateDuration();
  }

  saveShift() {
    if (!this.selectedShift.type_shift) {
      this.notify.showError('Vyberte typ smeny');
      return;
    }

    const payload = { ...this.selectedShift } as PlannedShift;

    // UPDATE
    if (payload.id) {
      this.plannerService.updateShift(payload.id, payload).subscribe({
        next: (saved) => this.handleSaveSuccess(saved),
        error: () => this.notify.showError('Chyba pri ukladaní')
      });
    }
    // CREATE
    else {
      this.plannerService.createShift(payload).subscribe({
        next: (saved) => this.handleSaveSuccess(saved),
        error: (err) => {
          this.notify.showError('Chyba: ' + (err.error?.non_field_errors?.[0] || 'Nepodarilo sa vytvoriť'));
        }
      });
    }
    this.isModalOpen = false
  }

  handleSaveSuccess(shift: PlannedShift) {
    this.notify.showSuccess('Uložené');
    this.closeModal();
    // Obnovíme dáta (aj tabuľku, aj spodný report)
    this.loadMonthData();
  }

  deleteShift() {
    if (this.selectedShift.id && confirm('Naozaj vymazať túto smenu?')) {
      this.plannerService.deleteShift(this.selectedShift.id).subscribe(() => {
        this.notify.showInfo('Smena vymazaná');
        this.closeModal();
        this.loadMonthData();
        this.isModalOpen = false
      });
    }
  }

  // --- TIME HELPERS ---
  private getLocalDateString(date: Date): string {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  hoursList: string[] = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));
  minutesList: string[] = ['00', '30'];

  tempStartH = '06'; tempStartM = '00';
  tempEndH = '14'; tempEndM = '00';
  computedDuration = '';

  parseTimeToSelects() {
    const s = this.selectedShift.custom_start;
    const e = this.selectedShift.custom_end;

    if (s) {
      const [h, m] = s.split(':');
      this.tempStartH = h;
      this.tempStartM = (m === '30') ? '30' : '00';
    }
    if (e) {
      const [h, m] = e.split(':');
      this.tempEndH = h;
      this.tempEndM = (m === '30') ? '30' : '00';
    }
  }

  updateTimeFromSelects(isStart: boolean) {
    if (isStart) {
      this.selectedShift.custom_start = `${this.tempStartH}:${this.tempStartM}`;
    } else {
      this.selectedShift.custom_end = `${this.tempEndH}:${this.tempEndM}`;
    }
    this.calculateDuration();
  }

  setPresetTime(start: string, end: string) {
    this.selectedShift.custom_start = start;
    this.selectedShift.custom_end = end;
    this.parseTimeToSelects();
    this.calculateDuration();
  }

  calculateDuration() {
    const s = this.selectedShift.custom_start;
    const e = this.selectedShift.custom_end;
    if (!s || !e) {
      this.computedDuration = '';
      return;
    }
    const [startH, startM] = s.split(':').map(Number);
    const [endH, endM] = e.split(':').map(Number);
    const startMinutes = startH * 60 + startM;
    let endMinutes = endH * 60 + endM;

    if (endMinutes < startMinutes) endMinutes += 24 * 60;

    const diff = endMinutes - startMinutes;
    this.computedDuration = `${Math.floor(diff / 60)} hod. ${diff % 60 > 0 ? (diff % 60) + ' min.' : ''}`;
  }

  isNextDay(): boolean {
    const s = this.selectedShift.custom_start;
    const e = this.selectedShift.custom_end;
    if (!s || !e) return false;
    return e < s;
  }
  currentYear: number = new Date().getFullYear();
  currentMonth: number = new Date().getMonth() + 1;

  // Premenné pre modálne okno kopírovania
  isCopyModalOpen = false;
  copySourceYear: number = new Date().getFullYear();
  copySourceMonth: number = 1;
  copyTargetYear: number = new Date().getFullYear();
  copyTargetMonth: number = 1;


  // Zoznam rokov a mesiacov pre dropdowny
  yearsList: number[] = [2024, 2025, 2026, 2027]; // Môžeš generovať dynamicky
  monthsList: { value: number; name: string }[] = [
    { value: 1, name: 'Január' }, { value: 2, name: 'Február' }, { value: 3, name: 'Marec' },
    { value: 4, name: 'Apríl' }, { value: 5, name: 'Máj' }, { value: 6, name: 'Jún' },
    { value: 7, name: 'Júl' }, { value: 8, name: 'August' }, { value: 9, name: 'September' },
    { value: 10, name: 'Október' }, { value: 11, name: 'November' }, { value: 12, name: 'December' }
  ];
  loadDataForMonth(year: number, month: number) {
    this.isLoading = true;

    // Tu musíte zavolať funkciu, ktorú už používate na načítanie smien.
    // Predpokladám, že v ngOnInit voláte niečo podobné:
    this.plannerService.getShifts(year, month).subscribe({ // Alebo getShifts, skontrolujte názov v service
      next: (data) => {
        // Tu priraďte dáta do vašej premennej (napr. this.shifts alebo this.matrix)
        // Príklad:
        // this.yearlyReport = data; // Ak používate yearly report
        // ALEBO
        // this.shifts = data;       // Ak máte pole smien

        // Ak máte inú metódu na refresh, zavolajte ju tu.

        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }
  // 2. Metóda na otvorenie okna
  openCopyModal() {
    // Prednastavíme Target na aktuálne zobrazený mesiac v plánovači
    this.copyTargetYear = this.currentYear;
    this.copyTargetMonth = this.currentMonth;

    // Prednastavíme Source na MINULÝ mesiac
    if (this.currentMonth === 1) {
      this.copySourceMonth = 12;
      this.copySourceYear = this.currentYear - 1;
    } else {
      this.copySourceMonth = this.currentMonth - 1;
      this.copySourceYear = this.currentYear;
    }

    this.isCopyModalOpen = true;
  }

  closeCopyModal() {
    this.isCopyModalOpen = false;
  }

  // 3. Metóda na vykonanie kopírovania
  submitCopy() {
    if (confirm(`Naozaj chcete skopírovať plán z ${this.copySourceMonth}/${this.copySourceYear} do ${this.copyTargetMonth}/${this.copyTargetYear}? Existujúce smeny nebudú prepísané.`)) {

      this.isLoading = true;

      this.plannerService.copyMonthlyPlan(
        this.copySourceYear,
        this.copySourceMonth,
        this.copyTargetYear,
        this.copyTargetMonth
      ).subscribe({
        next: (response: any) => {
          // OPRAVA TOASTU: Posielame objekt, nie dva parametre
          this.notify.showSuccess(response.message || 'Kopírovanie úspešné');

          this.isCopyModalOpen = false;

          // Obnovenie dát
          this.loadDataForMonth(this.currentYear, this.currentMonth);

          this.isLoading = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error(err);
          // OPRAVA TOASTU:
          this.notify.showError('Chyba pri kopírovaní plánu');

          this.isLoading = false;
          this.cdr.detectChanges();
        }
      });
    }
  }

  // Funkcia na odoslanie žiadosti
  requestExchange() {
    // ZMENA: Odstránili sme kontrolu '!this.selectedShift.change_reason'
    if (!this.selectedExchangeUser || !this.selectedShift.id) {
      this.notify.showError('Vyberte kolegu a uistite sa, že smena existuje.');
      return;
    }

    // Definujeme ID pre výmenu natvrdo
    const EXCHANGE_REASON_ID = 40;

    this.plannerService.requestExchange(
      this.selectedShift.id,
      this.selectedExchangeUser,
      EXCHANGE_REASON_ID // Posielame 40
    ).subscribe({
      next: () => {
        this.notify.showSuccess('Žiadosť o výmenu odoslaná.');
        this.closeModal();
        this.loadMonthData();
      },
      error: (err) => this.notify.showError(err.error.error || 'Chyba pri výmene.')
    });
  }
  // Funkcia pre Manažéra (Schválenie/Zamietnutie)
  decideExchange(status: 'approved' | 'rejected') {
    if (!this.selectedShift.id) return;

    this.plannerService.decideExchange(this.selectedShift.id, status, 'Rozhodnutie manažéra').subscribe({
      next: (res) => {
        this.notify.showInfo(res.detail);
        this.closeModal();
        this.loadMonthData();
      },
      error: () => this.notify.showError('Chyba pri spracovaní.')
    });
  }
  // Do triedy PlannerComponent pridaj túto funkciu:

  onExchangeModeChange() {
    const EXCHANGE_REASON_ID = 40; // ID pre "Výmena služby"

    if (this.isExchangeMode) {
      // Ak zaškrtol checkbox, nastavíme dôvod na 40
      this.selectedShift.change_reason = EXCHANGE_REASON_ID;
    } else {
      // Ak odškrtol, vymažeme dôvod (alebo ho vrátime na null)
      this.selectedShift.change_reason = null;
      this.selectedExchangeUser = null; // Vyčistíme aj vybraného kolegu
    }
  }

}
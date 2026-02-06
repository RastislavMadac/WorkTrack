import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AttendanceService } from '../../core/services/attendance.service';
import { AttendancePayload } from '../../shared/models/attendance.model';
import { HeaderComponent } from '../../core/components/header/header';
import { NotificationService } from '../../core/services/notification.service';
import { NavigationComponent } from '../../core/components/navigation/navigation';
import { AttendanceFormComponent } from './attendance-form/attendance-form';
import { AuthService } from '../../core/services/auth.service';
import { FormsModule } from '@angular/forms';
import { TypeShift } from '../../shared/models/typeShift.model';
@Component({
  selector: 'app-attendance-list',
  standalone: true,
  imports: [CommonModule, HeaderComponent, NavigationComponent, AttendanceFormComponent, FormsModule],
  templateUrl: './attendance.html',
  styleUrls: ['./attendance.scss']
})
export class AttendanceListComponent implements OnInit {

  selectedPeriod: string = new Date().toISOString().substring(0, 7);
  private attendanceService = inject(AttendanceService);
  private notify = inject(NotificationService);
  private authService = inject(AuthService);
  isModalOpen = false;
  currentUserId: number = 0;
  attendances = signal<any[]>([]);
  isLoading = signal(false);
  // Premenné pre oprávnenia
  isManager = false;
  isAdmin = false;
  ngOnInit() {
    this.currentUserId = Number(sessionStorage.getItem('user_id'));
    // Načítame role zo servisu
    this.isManager = this.authService.isManager();
    this.isAdmin = this.authService.isAdmin();
    this.loadData();
  }

  // Getter pre HTML šablónu - vráti true, ak je user Admin ALEBO Manager
  get canViewEmployees(): boolean {
    return this.isManager || this.isAdmin;
  }

  openAddModal() {
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
  }

  loadData() {
    this.isLoading.set(true);
    const [year, month] = this.selectedPeriod.split('-').map(Number);

    this.attendanceService.getAttendances(year, month).subscribe({
      next: (data) => {
        console.log('✅ Dáta prijaté z backendu:', data);
        this.attendances.set(data);
        this.sortData(); // Ak máme zapnuté triedenie, preusporiadame nové dáta
        this.isLoading.set(false);
      },
      error: () => {
        console.error('❌ Chyba backendu:'); // DEBUG - Pozri sem!
        this.notify.showError('Nepodarilo sa načítať dochádzku.');
        this.isLoading.set(false);
      }
    });
  }

  exportPdf() {
    const now = new Date();
    // Predpokladáme, že ID usera je v session (podľa tvojho AuthService)
    const userId = Number(sessionStorage.getItem('user_id'));
    this.attendanceService.downloadPdf(userId, now.getFullYear(), now.getMonth() + 1);
  }
  onSaveAttendance(payload: AttendancePayload) {
    this.attendanceService.createAttendance(payload).subscribe({
      next: () => {
        this.notify.showSuccess('Dochádzka úspešne zapísaná.');
        this.closeModal();
        this.loadData(); // Refresh tabuľky
      },
      error: (err) => {
        // Backend vráti chybu (napr. chýbajúci dôvod)
        const msg = err.error?.change_reason_id?.[0] || 'Chyba pri ukladaní.';
        this.notify.showError(msg);
      }
    });
  }

  // Získa názov smeny (napr. "Ranná") alebo vráti číslo/pomlčku
  getShiftName(typeShift: number | TypeShift | undefined | null): string {
    // Ak je to objekt a má property nameShift
    if (typeShift && typeof typeShift === 'object' && 'nameShift' in typeShift) {
      return typeShift.nameShift;
    }
    // Ak je to len ID (číslo) alebo iné
    return typeShift ? typeShift.toString() : '-';
  }

  // Získa CSS triedu podľa skratky (napr. "R", "N")
  getShiftShort(typeShift: number | TypeShift | undefined | null): string {
    if (typeShift && typeof typeShift === 'object' && 'shortName' in typeShift) {
      return typeShift.shortName;
    }
    return 'default';
  }

  // 👇 NOVÉ: Stav zoraďovania
  sortColumn: string = 'date'; // Defaultne podľa dátumu
  sortDirection: 'asc' | 'desc' = 'asc';

  // ... ngOnInit a loadData ostávajú rovnaké ...

  // 👇 NOVÁ METÓDA: Zavolá sa po kliknutí na hlavičku
  onSort(column: string) {
    // 1. Ak klikneme na ten istý stĺpec, otočíme smer
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      // 2. Ak klikneme na nový stĺpec, začneme 'asc'
      this.sortColumn = column;
      this.sortDirection = 'asc';
    }

    this.sortData();
  }

  // 👇 NOVÁ METÓDA: Vykoná samotné preusporiadanie poľa
  sortData() {
    this.attendances.update(items => {
      // Vytvoríme kópiu poľa, aby sme nemenili originál (immutability)
      return [...items].sort((a, b) => {
        let valA = this.getValueForSort(a, this.sortColumn);
        let valB = this.getValueForSort(b, this.sortColumn);

        // Ošetrenie null/undefined
        if (valA == null) valA = '';
        if (valB == null) valB = '';

        // Porovnanie
        let comparison = 0;
        if (valA > valB) comparison = 1;
        else if (valA < valB) comparison = -1;

        return this.sortDirection === 'asc' ? comparison : -comparison;
      });
    });
  }

  // Pomocná metóda na získanie hodnoty pre triedenie
  private getValueForSort(item: any, column: string): any {
    switch (column) {
      case 'date': return item.date;
      case 'employee': return item.employee_name || item.user; // Meno alebo ID
      case 'shift': return item.shift_name || '';
      case 'start': return item.custom_start || '';
      case 'end': return item.custom_end || '';
      case 'note': return item.note || '';
      default: return '';
    }
  }

  // Pomocná metóda pre HTML ikonu
  getSortIcon(column: string): string {
    if (this.sortColumn !== column) return '↕'; // Neutrálna ikona
    return this.sortDirection === 'asc' ? '▲' : '▼';
  }

  changeMonth(delta: number) {
    const [year, month] = this.selectedPeriod.split('-').map(Number);
    const date = new Date(year, month - 1 + delta, 1); // JS mesiace sú 0-11

    // Prevod späť na formát "YYYY-MM"
    const newYear = date.getFullYear();
    const newMonth = (date.getMonth() + 1).toString().padStart(2, '0');

    this.selectedPeriod = `${newYear}-${newMonth}`;
    this.loadData();
  }

  // 👇 NOVÉ: Metóda volaná pri zmene inputu
  onPeriodChange() {
    this.loadData();
  }

}
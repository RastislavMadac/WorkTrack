import { Component, EventEmitter, Input, Output, inject, OnInit, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlannerService } from '../../../core/services/plannedShift.service';
import { ChangeReasonService } from '../../../core/services/changeReason.service';
import { AuthService } from '../../../core/services/auth.service';
import { ChangeReason } from '../../../shared/models/changeReason.model';
import { PlannedShift } from '../../../shared/models/plannedShift.model';
import { AttendancePayload } from '../../../shared/models/attendance.model';
import { TypeShiftService } from '../../../core/services/tapeShift.service';
import { TypeShift } from '../../../shared/models/typeShift.model';
import { NotificationService } from '../../../core/services/notification.service';
import { User } from '../../../shared/models/user.model';

@Component({
  selector: 'app-attendance-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './attendance-form.html',
  styleUrls: ['./attendance-form.scss']
})
export class AttendanceFormComponent implements OnInit, OnChanges {
  @Input() userId!: number;
  @Input() isOpen = false;
  @Output() close = new EventEmitter<void>();
  @Output() save = new EventEmitter<AttendancePayload>();

  private plannerService = inject(PlannerService);
  private changeReasonService = inject(ChangeReasonService);
  private typeShiftService = inject(TypeShiftService);
  private authService = inject(AuthService);
  private notify = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);

  // Data
  reasons: ChangeReason[] = [];
  shiftTypes: TypeShift[] = [];
  users: User[] = [];

  // Form Model
  formDate: string = new Date().toISOString().split('T')[0];
  formStart: string = '';
  formEnd: string = '';
  formNote: string = '';
  selectedReasonId: number | null = null;
  selectedTypeId: number | null = null;

  // Logic state
  availablePlans: PlannedShift[] = [];
  selectedPlanId: number | null = null;
  selectedPlan: PlannedShift | null = null;

  isTimeChanged = false;
  canSelectUser = false;

  ngOnInit() {
    this.checkPermissions();
    this.loadDropdowns();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['isOpen'] && this.isOpen) {
      this.checkPermissions();
      this.resetForm();
      this.checkPlanForDate();
    }
  }

  checkPermissions() {
    this.canSelectUser = this.authService.isManager();
    // Načítame zoznam userov len raz
    if (this.canSelectUser && this.users.length === 0) {
      this.authService.getActiveUsers().subscribe(users => this.users = users);
    }
  }

  loadDropdowns() {
    this.changeReasonService.getReasons().subscribe(r => this.reasons = r);
    this.typeShiftService.getShiftTypes().subscribe(t => this.shiftTypes = t);
  }

  // 👇 OPRAVENÁ METÓDA: Prijíma parameter newUserId z HTML
  onUserChange(newUserId: any) {
    // 1. Aktualizujeme lokálne ID (pretypujeme na Number, lebo select vracia string)
    this.userId = Number(newUserId);

    // 2. Resetujeme výber plánu, aby sme nemiešali plány predchádzajúceho usera
    this.selectedPlan = null;
    this.selectedPlanId = null;

    // 3. Spustíme načítanie plánov pre NOVÉHO usera
    this.checkPlanForDate();
  }

  onDateChange() {
    this.checkPlanForDate();
  }

  onPlanSelectChange() {
    const plan = this.availablePlans.find(p => p.id == this.selectedPlanId);
    if (plan) {
      this.selectPlan(plan);
    } else {
      // Reset na "žiadny plán"
      this.selectedPlan = null;
      this.selectedTypeId = null;
      this.formStart = '';
      this.formEnd = '';
    }
    this.checkDiff();
  }

  checkPlanForDate() {
    this.availablePlans = [];

    if (!this.formDate || !this.userId) return;

    const dateObj = new Date(this.formDate);
    const year = dateObj.getFullYear();
    const month = dateObj.getMonth() + 1;

    this.plannerService.getShifts(year, month).subscribe({
      next: (shifts) => {
        // 1. Filtrujeme (User + Dátum + Nie je skrytá + Nie je Transferred)
        this.availablePlans = shifts.filter(s =>
          s.user === this.userId &&
          s.date === this.formDate &&
          !s.hidden &&
          !s.transferred
        );

        // 👇 ZMENA: Ak existuje ASPOŇ JEDEN plán, automaticky vyberieme prvý
        if (this.availablePlans.length > 0) {
          this.selectPlan(this.availablePlans[0]);
        } else {
          // Ak plán neexistuje, resetujeme výber
          this.selectedPlan = null;
          this.selectedPlanId = null;
          // Voliteľné: Vymazať aj časy, ak chceme čistý formulár
          // this.formStart = ''; 
          // this.formEnd = '';
        }

        this.checkDiff();
        this.cdr.detectChanges(); // Aktualizácia view
      },
      error: (err) => {
        console.error(err);
        this.cdr.detectChanges();
      }
    });
  }
  selectPlan(plan: PlannedShift) {
    this.selectedPlan = plan;
    this.selectedPlanId = plan.id!;
    this.selectedTypeId = typeof plan.type_shift === 'object' ? plan.type_shift.id : plan.type_shift;

    // Predvyplnenie časov
    this.formStart = plan.custom_start ? plan.custom_start.substring(0, 5) : '';
    this.formEnd = plan.custom_end ? plan.custom_end.substring(0, 5) : '';
  }

  checkDiff() {
    if (!this.selectedPlan) {
      this.isTimeChanged = true;
      return;
    }

    const planStart = this.selectedPlan.custom_start?.substring(0, 5);
    const planEnd = this.selectedPlan.custom_end?.substring(0, 5);

    if (this.formStart !== planStart || this.formEnd !== planEnd) {
      this.isTimeChanged = true;
    } else {
      this.isTimeChanged = false;
      this.selectedReasonId = null;
    }
  }

  onSave() {
    if (!this.formStart || !this.formEnd || !this.selectedTypeId) {
      this.notify.showError('Vyplňte časy a typ smeny.');
      return;
    }

    if (this.isTimeChanged && !this.selectedReasonId) {
      this.notify.showError('Časy sa líšia od plánu, musíte uviesť dôvod.');
      return;
    }

    const payload: AttendancePayload = {
      user: this.userId,
      date: this.formDate,
      type_shift: this.selectedTypeId,
      custom_start: this.formStart,
      custom_end: this.formEnd,
      note: this.formNote,
      planned_shift: this.selectedPlanId,
      change_reason_id: this.selectedReasonId
    };

    this.save.emit(payload);
  }

  resetForm() {
    this.formDate = new Date().toISOString().split('T')[0];
    this.formStart = '';
    this.formEnd = '';
    this.formNote = '';
    this.selectedReasonId = null;
    this.selectedTypeId = null;
    this.selectedPlan = null;
    this.selectedPlanId = null;
    this.availablePlans = [];
    this.isTimeChanged = false;
  }

  onClose() {
    this.close.emit();
  }
}
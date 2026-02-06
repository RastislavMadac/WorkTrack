import { ChangeDetectorRef, Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EmployeeService } from '../../../core/services/employee.service';
import { NotificationService } from '../../../core/services/notification.service';
import { AuthService } from '../../../core/services/auth.service';
import { EmployeePayload } from '../../../shared/models/employee.model';
import { HeaderComponent } from '../../../core/components/header/header';

@Component({
  selector: 'app-employee-list',
  standalone: true,
  imports: [CommonModule, FormsModule, HeaderComponent],
  templateUrl: './employee-list.html',
  styleUrls: ['./employee-list.scss']
})
export class EmployeeListComponent implements OnInit {
  employees: EmployeePayload[] = [];
  isLoading = false;
  isManager = false;


  isModalOpen = false;
  selectedEmployee: Partial<EmployeePayload> = {};
  isEditMode = false;

  private employeeService = inject(EmployeeService);
  private notify = inject(NotificationService);
  private authService = inject(AuthService);
  private cdr = inject(ChangeDetectorRef);
  ngOnInit() {
    this.isManager = this.authService.isManager();
    this.loadEmployees();
  }

  loadEmployees() {
    this.isLoading = true;
    this.employeeService.getEmployees().subscribe({
      next: (data) => {
        this.employees = data;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.notify.showError('Nepodarilo sa načítať zamestnancov.');
        this.isLoading = false;
        this.cdr.detectChanges()
      }
    });
  }

  openCreateModal() {
    this.selectedEmployee = {
      role: 'worker',
      initial_hours_balance: 0,
      is_active: true
    };
    this.isEditMode = false;
    this.isModalOpen = true;
  }

  openEditModal(employee: EmployeePayload) {

    this.selectedEmployee = { ...employee };
    this.isEditMode = true;
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
    this.selectedEmployee = {};
  }


  saveEmployee() {
    if (!this.selectedEmployee.username || !this.selectedEmployee.personal_number) {
      this.notify.showError('Vyplňte povinné polia (Meno, Osobné číslo).');
      return;
    }

    const payload = this.selectedEmployee as EmployeePayload;

    if (this.isEditMode && payload.id) {
      this.employeeService.updateEmployee(payload.id, payload).subscribe({
        next: () => {
          this.notify.showSuccess('Zamestnanec aktualizovaný.');


          setTimeout(() => {
            this.closeModal();
            this.loadEmployees();
          }, 0);
        },
        error: () => this.notify.showError('Chyba pri aktualizácii.')
      });
    } else {
      if (!payload.password) {
        this.notify.showError('Pri novom zamestnancovi je heslo povinné.');
        return;
      }
      this.employeeService.createEmployee(payload).subscribe({
        next: () => {
          this.notify.showSuccess('Zamestnanec vytvorený.');


          setTimeout(() => {
            this.closeModal();
            this.loadEmployees();
          }, 0);
        },
        error: (err) => {
          console.error(err);
          this.notify.showError('Chyba pri vytváraní.');
        }
      });
    }
  }

  deleteEmployee(id: number) {
    if (confirm('Naozaj chcete zmazať tohto zamestnanca?')) {
      this.employeeService.deleteEmployee(id).subscribe({
        next: () => {
          this.notify.showInfo('Zamestnanec bol odstránený.');


          setTimeout(() => {
            this.loadEmployees();
          }, 0);
        },
        error: () => this.notify.showError('Nemáte oprávnenie alebo nastala chyba.')
      });
    }
  }
}
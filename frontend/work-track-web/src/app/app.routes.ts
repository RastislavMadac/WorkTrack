import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login/login';
//import { PlannerComponent } from './features/planner/planner.component';
import { authGuard } from './core/guards/auth.guard';
import { DashboardComponent } from './core/components/dashboard/dashboard';
import { PlannerComponent } from './features/planner/planner';
import { EmployeeListComponent } from './features/employees/employee-list/employee-list';
import { AttendanceListComponent } from './features/attendance/attendance';

export const routes: Routes = [
    {
        path: 'login',
        component: LoginComponent
    },
    {
        path: 'dashboard',
        component: DashboardComponent,
        canActivate: [authGuard]
    },
    {
        path: 'attendance',
        component: AttendanceListComponent,
        canActivate: [authGuard]
    },
    {
        path: 'planner',
        component: PlannerComponent,
        canActivate: [authGuard]
    },
    {
        path: 'employees',
        component: EmployeeListComponent,
        canActivate: [authGuard]
    },
    {
        path: 'login',
        component: LoginComponent
    },
    // ... ostatné routy
    {
        path: '',
        redirectTo: '/login', // Zmenené z '/planner' na '/login'
        pathMatch: 'full'
    },
    {
        path: '**',
        redirectTo: '/login'
    }
];
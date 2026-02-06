import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service'; // Importuj tvoju novú service
import { NotificationService } from '../../../core/services/notification.service';
import { HttpErrorResponse } from '@angular/common/http';
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrls: ['./login.scss']
})
export class LoginComponent {
  username = '';
  password = '';
  errorMessage = '';
  isLoading = false;
  // Injektujeme Service a Router
  private authService = inject(AuthService);
  private router = inject(Router);
  private notify = inject(NotificationService);

  onLogin() {
    this.isLoading = true;

    this.authService.login({ username: this.username, password: this.password })
      .subscribe({
        next: () => {
          this.notify.showSuccess('Prihlásenie úspešné');
          this.router.navigate(['/dashboard']);
        },
        error: (err: HttpErrorResponse) => {
          this.isLoading = false;

          // DEBUG: Pozri sa do konzoly (F12), či sa toto vypíše
          console.log('❌ Komponent prijal chybu:', err.status);

          if (err.status === 400) {
            // Tu voláme notifikáciu
            this.notify.showError('Nesprávne meno alebo heslo.');
          }
        }
      });
  }
}
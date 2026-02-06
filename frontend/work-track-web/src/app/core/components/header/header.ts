import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router'; // RouterModule pre linky
import { AuthService } from '../../services/auth.service';
import { NavigationComponent } from '../navigation/navigation';
@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, RouterModule, NavigationComponent],
  templateUrl: './header.html',
  styleUrls: ['./header.scss']
})
export class HeaderComponent {
  private authService = inject(AuthService);

  // Getter na získanie mena (vždy aktuálne)
  get username(): string {
    return this.authService.getFullName();
  }

  // Getter na zistenie, či sme prihlásení (aby sa header nezobrazil na Login stránke)
  get isLoggedIn(): boolean {
    return this.authService.isAuthenticated();
  }

  logout() {
    this.authService.logout();
  }
}
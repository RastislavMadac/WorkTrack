import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NotificationService, Notification } from '../../../core/services/notification.service';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './toast.html',
  styleUrls: ['./toast.scss']
})
export class ToastComponent implements OnInit {
  notification: Notification | null = null;
  private timeoutId: any;

  // Injektujeme službu
  private notificationService = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);
  ngOnInit() {
    this.notificationService.notification$.subscribe(notif => {
      // Pridáme log, aby si videl, či správa prišla
      console.log('🔔 Toast prijal správu:', notif);

      this.notification = notif;
      this.cdr.detectChanges();
      if (notif) {
        // Reset časovača pri novej správe
        clearTimeout(this.timeoutId);
        // Zatvorenie po 4 sekundách
        this.timeoutId = setTimeout(() => this.close(), 4000);
      }
    });
  }

  close() {
    this.notification = null;
    this.notificationService.clear();
  }
}
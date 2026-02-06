import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-navigation',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './navigation.html',
  styleUrls: ['./navigation.scss']
})
export class NavigationComponent {


  menuItems = [
    { label: 'Plánovač', link: '/planner', },
    { label: 'Zamestnanci', link: '/employees' },
    { label: 'Dochádzka', link: '/attendance' }
  ];

}
import { Component, ChangeDetectionStrategy } from '@angular/core';
import { AppShellComponent } from '../../shared/components/app-shell/app-shell.component';

@Component({
  selector: 'app-system',
  standalone: true,
  imports: [AppShellComponent],
  templateUrl: './system.component.html',
  styleUrl: './system.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SystemComponent {}

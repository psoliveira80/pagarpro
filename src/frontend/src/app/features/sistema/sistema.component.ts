import { Component, ChangeDetectionStrategy } from '@angular/core';
import { AppShellComponent } from '../../shared/components/app-shell/app-shell.component';

@Component({
  selector: 'app-sistema',
  standalone: true,
  imports: [AppShellComponent],
  templateUrl: './sistema.component.html',
  styleUrl: './sistema.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SistemaComponent {}

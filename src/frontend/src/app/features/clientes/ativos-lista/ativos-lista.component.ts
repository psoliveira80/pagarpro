import {
  Component,
  ChangeDetectionStrategy,
  input,
} from '@angular/core';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';

@Component({
  selector: 'app-ativos-lista',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './ativos-lista.component.html',
  styleUrl: './ativos-lista.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AtivosListaComponent {
  readonly customerId = input.required<string>();
}

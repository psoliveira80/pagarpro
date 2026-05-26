import {
  Component,
  ChangeDetectionStrategy,
  input,
} from '@angular/core';
import { UiIconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-assets-list',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './assets-list.component.html',
  styleUrl: './assets-list.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssetsListComponent {
  readonly customerId = input.required<string>();
}

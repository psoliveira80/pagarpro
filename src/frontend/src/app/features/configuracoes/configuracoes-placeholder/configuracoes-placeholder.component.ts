import { Component, ChangeDetectionStrategy, computed, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import { UiIconComponent } from '../../../shared/components/icon/icon.component';

@Component({
  selector: 'app-configuracoes-placeholder',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './configuracoes-placeholder.component.html',
  styleUrl: './configuracoes-placeholder.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfiguracoesPlaceholderComponent {
  private readonly route = inject(ActivatedRoute);

  private readonly urlSegments = toSignal(
    this.route.url.pipe(map((segments) => segments.map((s) => s.path))),
    { initialValue: [] as string[] },
  );

  private readonly labelMap: Record<string, string> = {
    users: 'Usuários',
    roles: 'Roles & Permissões',
    finance: 'Financeiro',
    contracts: 'Contratos',
    general: 'Geral',
  };

  readonly settingName = computed(() => {
    const segments = this.urlSegments();
    const last = segments[segments.length - 1] ?? '';
    return this.labelMap[last] ?? last;
  });
}

import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { ToastService } from '../../shared/components/toast/toast.service';
import { AdminService } from '../../core/services/admin.service';

@Component({
  selector: 'app-contract-settings',
  standalone: true,
  imports: [],
  templateUrl: './contract-settings.component.html',
  styleUrl: './contract-settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContractSettingsComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly toastService = inject(ToastService);

  readonly isLoading = signal(true);
  readonly isSaving = signal(false);

  // Contrato defaults
  readonly defaultFrequency = signal('mensal');
  readonly defaultPaymentMethod = signal('pix');
  readonly autoGenerateInstallments = signal(true);
  readonly clausesTemplate = signal('');
  readonly defaultContractDurationMonths = signal('12');

  async ngOnInit(): Promise<void> {
    this.isLoading.set(true);
    try {
      const settings = await this.adminService.getSettings();
      const contracts = settings.find((s) => s.key === 'contracts');
      if (contracts?.value) {
        const v = contracts.value;
        if (v['default_frequency'] != null) this.defaultFrequency.set(String(v['default_frequency']));
        if (v['default_payment_method'] != null) this.defaultPaymentMethod.set(String(v['default_payment_method']));
        if (v['auto_generate_installments'] != null) this.autoGenerateInstallments.set(!!v['auto_generate_installments']);
        if (v['clauses_template'] != null) this.clausesTemplate.set(String(v['clauses_template']));
        if (v['default_duration_months'] != null) this.defaultContractDurationMonths.set(String(v['default_duration_months']));
      }
    } catch {
      this.toastService.show({ message: 'Erro ao carregar configurações de contratos', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  async save(): Promise<void> {
    this.isSaving.set(true);
    try {
      await this.adminService.updateSettings({
        contracts: {
          default_frequency: this.defaultFrequency(),
          default_payment_method: this.defaultPaymentMethod(),
          auto_generate_installments: this.autoGenerateInstallments(),
          clauses_template: this.clausesTemplate(),
          default_duration_months: parseInt(this.defaultContractDurationMonths(), 10),
        },
      });
      this.toastService.show({ message: 'Configurações de contratos salvas', type: 'success' });
    } catch {
      this.toastService.show({ message: 'Erro ao salvar configurações', type: 'error' });
    } finally {
      this.isSaving.set(false);
    }
  }

  toggleAutoGenerate(): void {
    this.autoGenerateInstallments.update((v) => !v);
  }
}

import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { ToastService } from '../../shared/components/toast/toast.service';
import { AdminService } from '../../core/services/admin.service';

@Component({
  selector: 'app-finance-settings',
  standalone: true,
  imports: [],
  templateUrl: './finance-settings.component.html',
  styleUrl: './finance-settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FinanceSettingsComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly toastService = inject(ToastService);

  readonly isLoading = signal(true);
  readonly isSaving = signal(false);

  // Finance params
  readonly interestRate = signal('2.0');
  readonly fineRate = signal('2.0');
  readonly discountDays = signal('5');
  readonly discountPercent = signal('5.0');
  readonly defaultPaymentMethod = signal('pix');
  readonly gracePeriodDays = signal('0');

  async ngOnInit(): Promise<void> {
    this.isLoading.set(true);
    try {
      const settings = await this.adminService.getSettings();
      const finance = settings.find((s) => s.key === 'finance');
      if (finance?.value) {
        const v = finance.value;
        if (v['interest_rate'] != null) this.interestRate.set(String(v['interest_rate']));
        if (v['fine_rate'] != null) this.fineRate.set(String(v['fine_rate']));
        if (v['discount_days'] != null) this.discountDays.set(String(v['discount_days']));
        if (v['discount_percent'] != null) this.discountPercent.set(String(v['discount_percent']));
        if (v['default_payment_method'] != null) this.defaultPaymentMethod.set(String(v['default_payment_method']));
        if (v['grace_period_days'] != null) this.gracePeriodDays.set(String(v['grace_period_days']));
      }
    } catch {
      this.toastService.show({ message: 'Erro ao carregar configurações financeiras', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }

  async save(): Promise<void> {
    this.isSaving.set(true);
    try {
      await this.adminService.updateSettings({
        finance: {
          interest_rate: parseFloat(this.interestRate()),
          fine_rate: parseFloat(this.fineRate()),
          discount_days: parseInt(this.discountDays(), 10),
          discount_percent: parseFloat(this.discountPercent()),
          default_payment_method: this.defaultPaymentMethod(),
          grace_period_days: parseInt(this.gracePeriodDays(), 10),
        },
      });
      this.toastService.show({ message: 'Configurações financeiras salvas', type: 'success' });
    } catch {
      this.toastService.show({ message: 'Erro ao salvar configurações', type: 'error' });
    } finally {
      this.isSaving.set(false);
    }
  }
}

import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-resend-verification',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ToastComponent],
  templateUrl: './resend-verification.component.html',
  styleUrl: './resend-verification.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResendVerificationComponent {
  private readonly http = inject(HttpClient);
  private readonly toastService = inject(ToastService);

  readonly productName = environment.productName;
  readonly isLoading = signal(false);
  readonly sent = signal(false);

  readonly email = new FormControl('', {
    validators: [Validators.required, Validators.email],
    nonNullable: true,
  });

  async onSubmit(): Promise<void> {
    if (this.email.invalid || this.isLoading()) return;

    this.isLoading.set(true);
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiBaseUrl}/auth/resend-verification`, {
          email: this.email.value,
        }),
      );
      this.sent.set(true);
      this.toastService.show({
        message: 'Se o e-mail existir, um link de verificação foi enviado.',
        type: 'success',
      });
    } catch {
      this.toastService.show({ message: 'Erro ao processar solicitação', type: 'error' });
    } finally {
      this.isLoading.set(false);
    }
  }
}

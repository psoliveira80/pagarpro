import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ToastComponent],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgotPasswordComponent {
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
        this.http.post(`${environment.apiBaseUrl}/auth/password/forgot`, {
          email: this.email.value,
        }),
      );
      this.sent.set(true);
      this.toastService.show({
        message: 'Se o e-mail existir, um link de redefinição foi enviado.',
        type: 'success',
      });
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 429) {
        this.toastService.show({
          message: 'Muitas tentativas. Tente novamente mais tarde.',
          type: 'warning',
        });
      } else {
        this.toastService.show({ message: 'Erro ao processar solicitação', type: 'error' });
      }
    } finally {
      this.isLoading.set(false);
    }
  }
}

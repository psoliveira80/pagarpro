import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormGroup, FormControl, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ToastComponent],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResetPasswordComponent {
  private readonly http = inject(HttpClient);
  private readonly toastService = inject(ToastService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly productName = environment.productName;
  readonly isLoading = signal(false);

  readonly form = new FormGroup({
    password: new FormControl('', {
      validators: [Validators.required, Validators.minLength(8)],
      nonNullable: true,
    }),
    confirmPassword: new FormControl('', {
      validators: [Validators.required],
      nonNullable: true,
    }),
  });

  get passwordsMismatch(): boolean {
    return (
      this.form.controls.confirmPassword.touched &&
      this.form.controls.password.value !== this.form.controls.confirmPassword.value
    );
  }

  async onSubmit(): Promise<void> {
    if (this.form.invalid || this.passwordsMismatch || this.isLoading()) return;

    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.toastService.show({ message: 'Token inválido', type: 'error' });
      return;
    }

    this.isLoading.set(true);
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiBaseUrl}/auth/password/reset`, {
          token,
          new_password: this.form.controls.password.value,
        }),
      );
      this.toastService.show({ message: 'Senha redefinida com sucesso!', type: 'success' });
      await this.router.navigate(['/auth/login']);
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 400) {
        this.toastService.show({ message: 'Token inválido ou expirado', type: 'error' });
      } else {
        this.toastService.show({ message: 'Erro ao redefinir senha', type: 'error' });
      }
    } finally {
      this.isLoading.set(false);
    }
  }
}

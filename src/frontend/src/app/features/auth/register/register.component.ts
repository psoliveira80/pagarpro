import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormGroup, FormControl, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ToastComponent],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegisterComponent {
  private readonly http = inject(HttpClient);
  private readonly toastService = inject(ToastService);

  readonly productName = environment.productName;
  readonly isDevMode = !environment.production;
  readonly isLoading = signal(false);
  readonly step = signal(1);
  readonly showPassword = signal(false);
  readonly showConfirmPassword = signal(false);

  readonly form = new FormGroup({
    nome_completo: new FormControl('', {
      validators: [Validators.required, Validators.minLength(3)],
      nonNullable: true,
    }),
    email: new FormControl('', {
      validators: [Validators.required, Validators.email],
      nonNullable: true,
    }),
    password: new FormControl('', {
      validators: [Validators.required, Validators.minLength(8), Validators.pattern(/^(?=.*[A-Z])(?=.*\d).{8,}$/)],
      nonNullable: true,
    }),
    password_confirmation: new FormControl('', {
      validators: [Validators.required],
      nonNullable: true,
    }),
  });

  get passwordsMismatch(): boolean {
    return (
      this.form.controls.password_confirmation.touched &&
      this.form.controls.password.value !== this.form.controls.password_confirmation.value
    );
  }

  get step1Valid(): boolean {
    return this.form.controls.nome_completo.valid && this.form.controls.email.valid;
  }

  get step2Valid(): boolean {
    return (
      this.form.controls.password.valid &&
      this.form.controls.password_confirmation.valid &&
      !this.passwordsMismatch
    );
  }

  nextStep(): void {
    if (this.step() === 1 && this.step1Valid) {
      this.step.set(2);
    }
  }

  prevStep(): void {
    if (this.step() === 2) {
      this.step.set(1);
    }
  }

  togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  toggleConfirmPassword(): void {
    this.showConfirmPassword.update((v) => !v);
  }

  async onSubmit(): Promise<void> {
    if (this.form.invalid || this.passwordsMismatch || this.isLoading()) return;

    this.isLoading.set(true);
    try {
      await firstValueFrom(
        this.http.post(`${environment.apiBaseUrl}/auth/register`, {
          nome_completo: this.form.controls.nome_completo.value,
          email: this.form.controls.email.value,
          password: this.form.controls.password.value,
          password_confirmation: this.form.controls.password_confirmation.value,
        }),
      );
      this.step.set(3);
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 409) {
        this.toastService.show({ message: 'E-mail já cadastrado', type: 'error' });
        this.step.set(1);
      } else if (err instanceof HttpErrorResponse && err.status === 422) {
        this.toastService.show({ message: err.error?.detail || 'Dados inválidos', type: 'error' });
      } else {
        this.toastService.show({ message: 'Erro ao criar conta', type: 'error' });
      }
    } finally {
      this.isLoading.set(false);
    }
  }
}

import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  ViewChild,
  ElementRef,
  AfterViewInit,
} from '@angular/core';
import { ReactiveFormsModule, FormGroup, FormControl, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';

import { AuthService } from '../../../core/services/auth.service';
import { ToastService } from '../../../shared/components/toast/toast.service';
import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, ToastComponent],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent implements AfterViewInit {
  private readonly authService = inject(AuthService);
  private readonly toastService = inject(ToastService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  @ViewChild('emailInput') emailInput!: ElementRef<HTMLInputElement>;

  readonly productName = environment.productName;
  readonly isLoading = signal(false);
  readonly showPassword = signal(false);

  readonly form = new FormGroup({
    email: new FormControl('admin@example.com', {
      validators: [Validators.required, Validators.email],
      nonNullable: true,
    }),
    password: new FormControl('Admin@123', {
      validators: [Validators.required, Validators.minLength(8)],
      nonNullable: true,
    }),
  });

  ngAfterViewInit(): void {
    this.emailInput?.nativeElement.focus();
  }

  togglePassword(): void {
    this.showPassword.update((v) => !v);
  }

  async onSubmit(): Promise<void> {
    if (this.form.invalid || this.isLoading()) return;

    this.isLoading.set(true);

    try {
      await this.authService.login(
        this.form.controls.email.value,
        this.form.controls.password.value,
      );
      const redirect = this.route.snapshot.queryParamMap.get('redirect') || '/sistema/dashboard';
      await this.router.navigateByUrl(redirect);
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 401) {
        this.toastService.show({ message: 'Credenciais inválidas', type: 'error' });
      } else if (err instanceof HttpErrorResponse && err.status === 403) {
        this.toastService.show({
          message: 'Verifique seu e-mail antes de entrar',
          type: 'warning',
        });
      } else if (err instanceof HttpErrorResponse && err.status === 429) {
        this.toastService.show({
          message: 'Muitas tentativas. Tente novamente mais tarde.',
          type: 'warning',
        });
      } else {
        this.toastService.show({ message: 'Erro ao conectar ao servidor', type: 'error' });
      }
      this.emailInput?.nativeElement.focus();
    } finally {
      this.isLoading.set(false);
    }
  }
}

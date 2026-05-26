import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ToastComponent } from '../../../shared/components/toast/toast.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [RouterLink, ToastComponent],
  templateUrl: './verify-email.component.html',
  styleUrl: './verify-email.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VerifyEmailComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly productName = environment.productName;
  readonly isLoading = signal(true);
  readonly success = signal(false);
  readonly errorMessage = signal('');

  async ngOnInit(): Promise<void> {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.isLoading.set(false);
      this.errorMessage.set('Token não fornecido');
      return;
    }

    try {
      await firstValueFrom(
        this.http.post(`${environment.apiBaseUrl}/auth/verify-email`, { token }),
      );
      this.success.set(true);
      // Auto-redirect to login after 3s
      setTimeout(() => {
        this.router.navigate(['/auth/login']);
      }, 3000);
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 400) {
        this.errorMessage.set('Token inválido ou expirado');
      } else {
        this.errorMessage.set('Erro ao verificar e-mail');
      }
    } finally {
      this.isLoading.set(false);
    }
  }
}

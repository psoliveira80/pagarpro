import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
} from '@angular/core';
import { Router } from '@angular/router';
import { UiIconComponent } from '../../shared/components/icon/icon.component';
import {
  ReportService,
  ReportDefinition,
  SavedReport,
} from '../../core/services/report.service';

@Component({
  selector: 'app-reports-list',
  standalone: true,
  imports: [UiIconComponent],
  templateUrl: './reports-list.component.html',
  styleUrl: './reports-list.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReportsListComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly reportService = inject(ReportService);

  readonly builtInReports: ReportDefinition[] =
    this.reportService.builtInReports;
  readonly savedReports = signal<SavedReport[]>([]);
  readonly isLoading = signal(false);

  ngOnInit(): void {
    this.loadSavedReports();
  }

  async loadSavedReports(): Promise<void> {
    this.isLoading.set(true);
    try {
      const reports = await this.reportService.listSavedReports();
      this.savedReports.set(reports);
    } catch {
      // Ignore — saved reports are optional
    } finally {
      this.isLoading.set(false);
    }
  }

  openReport(slug: string): void {
    this.router.navigate(['/system/reports', slug]);
  }

  openBuilder(): void {
    this.router.navigate(['/system/reports', 'builder']);
  }
}

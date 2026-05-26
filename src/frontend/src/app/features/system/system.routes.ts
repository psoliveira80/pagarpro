import { Routes } from '@angular/router';
import { SystemComponent } from './system.component';

export const SYSTEM_ROUTES: Routes = [
  {
    path: '',
    component: SystemComponent,
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('../dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'customers',
        loadComponent: () =>
          import('../customers/customers-list.component').then((m) => m.CustomersListComponent),
      },
      {
        path: 'customers/new',
        loadComponent: () =>
          import('../customers/customer-wizard.component').then(
            (m) => m.CustomerWizardComponent,
          ),
      },
      {
        path: 'customers/import',
        loadComponent: () =>
          import('../customers/import-customers.component').then(
            (m) => m.ImportCustomersComponent,
          ),
      },
      {
        path: 'customers/:id/edit',
        loadComponent: () =>
          import('../customers/customer-wizard.component').then(
            (m) => m.CustomerWizardComponent,
          ),
      },
      {
        path: 'customers/:id',
        loadComponent: () =>
          import('../customers/customer-detail.component').then(
            (m) => m.CustomerDetailComponent,
          ),
      },
      {
        path: 'vehicles',
        loadComponent: () =>
          import('../vehicles/vehicles-list.component').then(
            (m) => m.VehiclesListComponent,
          ),
      },
      {
        path: 'vehicles/new',
        loadComponent: () =>
          import('../vehicles/vehicle-wizard.component').then(
            (m) => m.VehicleWizardComponent,
          ),
      },
      {
        path: 'map',
        loadComponent: () =>
          import('../vehicles/fleet-map.component').then(
            (m) => m.FleetMapComponent,
          ),
      },
      {
        path: 'contracts',
        loadComponent: () =>
          import('../contracts/contracts-list.component').then(
            (m) => m.ContractsListComponent,
          ),
      },
      {
        path: 'contracts/new',
        loadComponent: () =>
          import('../contracts/contract-wizard.component').then(
            (m) => m.ContractWizardComponent,
          ),
      },
      {
        path: 'contracts/:id',
        loadComponent: () =>
          import('../contracts/contract-detail.component').then(
            (m) => m.ContractDetailComponent,
          ),
      },
      {
        path: 'finance/receivables',
        loadComponent: () =>
          import('../finance/receivables-list.component').then(
            (m) => m.ReceivablesListComponent,
          ),
      },
      {
        path: 'finance/validation-queue',
        loadComponent: () =>
          import('../finance/validation-queue.component').then(
            (m) => m.ValidationQueueComponent,
          ),
      },
      {
        path: 'finance/payables',
        loadComponent: () =>
          import('../finance/payables-list.component').then(
            (m) => m.PayablesListComponent,
          ),
      },
      {
        path: 'finance/recurring',
        loadComponent: () =>
          import('../finance/recurring-templates.component').then(
            (m) => m.RecurringTemplatesComponent,
          ),
      },
      {
        path: 'finance/dre',
        loadComponent: () =>
          import('../finance/dre-report.component').then(
            (m) => m.DreReportComponent,
          ),
      },
      {
        path: 'finance/bank-accounts',
        loadComponent: () =>
          import('../finance/bank-accounts-list.component').then(
            (m) => m.BankAccountsListComponent,
          ),
      },
      {
        path: 'finance/bank-import',
        loadComponent: () =>
          import('../finance/bank-import.component').then(
            (m) => m.BankImportComponent,
          ),
      },
      {
        path: 'finance/reconciliation',
        loadComponent: () =>
          import('../finance/reconciliation.component').then(
            (m) => m.ReconciliationComponent,
          ),
      },
      {
        path: 'finance/divergences',
        loadComponent: () =>
          import('../finance/divergences.component').then(
            (m) => m.DivergencesComponent,
          ),
      },
      {
        path: 'inbox',
        loadComponent: () =>
          import('../inbox/whatsapp-inbox.component').then(
            (m) => m.WhatsappInboxComponent,
          ),
      },
      {
        path: 'inbox/broadcasts',
        loadComponent: () =>
          import('../inbox/broadcast-list.component').then(
            (m) => m.BroadcastListComponent,
          ),
      },
      {
        path: 'reports',
        loadComponent: () =>
          import('../reports/reports-list.component').then(
            (m) => m.ReportsListComponent,
          ),
      },
      {
        path: 'reports/builder',
        loadComponent: () =>
          import('../reports/report-builder.component').then(
            (m) => m.ReportBuilderComponent,
          ),
      },
      {
        path: 'reports/:type',
        loadComponent: () =>
          import('../reports/report-viewer.component').then(
            (m) => m.ReportViewerComponent,
          ),
      },
      {
        path: 'settings/agent',
        loadComponent: () =>
          import('../settings/agent-config.component').then(
            (m) => m.AgentConfigComponent,
          ),
      },
      {
        path: 'settings/users',
        loadComponent: () =>
          import('../settings/settings-placeholder.component').then(
            (m) => m.SettingsPlaceholderComponent,
          ),
      },
      {
        path: 'settings/roles',
        loadComponent: () =>
          import('../settings/settings-placeholder.component').then(
            (m) => m.SettingsPlaceholderComponent,
          ),
      },
      {
        path: 'settings/finance',
        loadComponent: () =>
          import('../settings/finance-settings.component').then(
            (m) => m.FinanceSettingsComponent,
          ),
      },
      {
        path: 'settings/contracts',
        loadComponent: () =>
          import('../settings/contract-settings.component').then(
            (m) => m.ContractSettingsComponent,
          ),
      },
      {
        path: 'settings/general',
        loadComponent: () =>
          import('../settings/integrations.component').then(
            (m) => m.IntegrationsComponent,
          ),
      },
      {
        path: 'settings/integrations',
        loadComponent: () =>
          import('../settings/integrations.component').then(
            (m) => m.IntegrationsComponent,
          ),
      },
      {
        path: 'settings/audit-log',
        loadComponent: () =>
          import('../settings/audit-log.component').then(
            (m) => m.AuditLogComponent,
          ),
      },
      {
        path: 'settings/modules',
        loadComponent: () =>
          import('../settings/modules.component').then(
            (m) => m.ModulesComponent,
          ),
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('../settings/settings-placeholder.component').then(
            (m) => m.SettingsPlaceholderComponent,
          ),
      },
      {
        path: 'preferences',
        loadComponent: () =>
          import('../settings/settings-placeholder.component').then(
            (m) => m.SettingsPlaceholderComponent,
          ),
      },
      {
        path: 'security',
        loadComponent: () =>
          import('../settings/settings-placeholder.component').then(
            (m) => m.SettingsPlaceholderComponent,
          ),
      },
    ],
  },
];

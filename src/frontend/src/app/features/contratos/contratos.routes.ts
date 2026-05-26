import { Routes } from '@angular/router';

export const CONTRATOS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./contratos-lista/contratos-lista.component').then((m) => m.ContratosListaComponent),
  },
  {
    path: 'novo',
    loadComponent: () =>
      import('./contrato-wizard/contrato-wizard.component').then((m) => m.ContratoWizardComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./contrato-detalhe/contrato-detalhe.component').then((m) => m.ContratoDetalheComponent),
  },
];

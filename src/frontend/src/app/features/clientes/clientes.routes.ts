import { Routes } from '@angular/router';

export const CLIENTES_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./clientes-lista/clientes-lista.component').then((m) => m.ClientesListaComponent),
  },
  {
    path: 'novo',
    loadComponent: () =>
      import('./cliente-wizard/cliente-wizard.component').then((m) => m.ClienteWizardComponent),
  },
  {
    path: 'importar',
    loadComponent: () =>
      import('./importar-clientes/importar-clientes.component').then((m) => m.ImportarClientesComponent),
  },
  {
    path: ':id/editar',
    loadComponent: () =>
      import('./cliente-wizard/cliente-wizard.component').then((m) => m.ClienteWizardComponent),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./cliente-detalhe/cliente-detalhe.component').then((m) => m.ClienteDetalheComponent),
  },
];

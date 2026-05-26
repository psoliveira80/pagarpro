import { Routes } from '@angular/router';

export const VEICULOS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./veiculos-lista/veiculos-lista.component').then((m) => m.VeiculosListaComponent),
  },
  {
    path: 'novo',
    loadComponent: () =>
      import('./veiculo-wizard/veiculo-wizard.component').then((m) => m.VeiculoWizardComponent),
  },
  {
    path: 'mapa',
    loadComponent: () =>
      import('./frota-mapa/frota-mapa.component').then((m) => m.FrotaMapaComponent),
  },
];

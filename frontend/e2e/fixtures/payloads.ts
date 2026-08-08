export const SALA_BASE = {
  largo: 8.5,
  ancho: 6.0,
  alto: 3.0,
  superficies: [
    { material: "Concreto" },
    { material: "Concreto" },
    { material: "Cartón-yeso" },
    { material: "Cartón-yeso" },
    { material: "Parquet sobre hormigón" },
    { material: "Concreto" },
  ],
};

export const SALA_CON_USO = {
  ...SALA_BASE,
  uso: "home_studio",
};

export const SALA_CUBICA = {
  largo: 5,
  ancho: 5,
  alto: 5,
  superficies: Array(6).fill({ material: "Concreto" }),
};

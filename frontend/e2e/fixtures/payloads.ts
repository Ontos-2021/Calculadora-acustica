export const SALA_BASE = {
  largo: 8.5,
  ancho: 6.0,
  alto: 3.0,
  superficies: [
    { material: "Concreto" },
    { material: "Madera" },
    { material: "Yeso" },
    { material: "Vidrio" },
    { material: "Alfombra gruesa" },
    { material: "Panel acústico" },
  ],
  environment: { temperature_c: 20, relative_humidity: 50, pressure_pa: 101325 },
  include_air_attenuation: false,
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
  environment: { temperature_c: 20, relative_humidity: 50, pressure_pa: 101325 },
};

export enum Species {
  Plant = "plant",
  Herbivore = "herbivore",
  Predator = "predator",
}

export interface Entity {
  id: number;
  species: Species;
  x: number;
  y: number;
  energy: number;
  /** Current movement direction in radians (ignored for plants) */
  direction: number;
}

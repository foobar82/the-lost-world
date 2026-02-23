export const Species = {
  Plant: "plant",
  Herbivore: "herbivore",
  Predator: "predator",
} as const;

export type Species = (typeof Species)[keyof typeof Species];

export interface Entity {
  id: number;
  species: Species;
  x: number;
  y: number;
  energy: number;
  /** Current movement direction in radians (ignored for plants) */
  direction: number;
}

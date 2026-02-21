export type Species = "plant" | "herbivore" | "predator";

export interface Entity {
  id: number;
  species: Species;
  x: number;
  y: number;
  energy: number;
  alive: boolean;
}

export interface SimulationState {
  entities: Entity[];
  nextId: number;
  tickCount: number;
}

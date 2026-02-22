import type { Entity } from "./types";
import { Species } from "./types";
import {
  INITIAL_PLANTS,
  INITIAL_HERBIVORES,
  INITIAL_PREDATORS,
  PLANT_CAP,
  HERBIVORE_CAP,
  PREDATOR_CAP,
  RESPAWN_COUNT,
  MAX_ENERGY,
  PLANT_ENERGY_REGEN,
  PLANT_ENERGY_DRAIN,
} from "./constants";
import {
  createEntity,
  updatePlant,
  updateHerbivore,
  updatePredator,
} from "./entities";
import type { IdCounter } from "./entities";

export class Simulation {
  entities: Entity[] = [];
  private ids: IdCounter = { value: 1 };

  constructor() {
    this.seed();
  }

  private seed(): void {
    for (let i = 0; i < INITIAL_PLANTS; i++) {
      this.entities.push(createEntity(Species.Plant, this.ids));
    }
    for (let i = 0; i < INITIAL_HERBIVORES; i++) {
      this.entities.push(createEntity(Species.Herbivore, this.ids));
    }
    for (let i = 0; i < INITIAL_PREDATORS; i++) {
      this.entities.push(createEntity(Species.Predator, this.ids));
    }
  }

  tick(): void {
    const newEntities: Entity[] = [];

    const plants = this.entities.filter((e) => e.species === Species.Plant);
    const herbivores = this.entities.filter((e) => e.species === Species.Herbivore);
    const predators = this.entities.filter((e) => e.species === Species.Predator);

    // Update predators first (they eat herbivores)
    for (const pred of predators) {
      updatePredator(pred, herbivores, newEntities, this.ids);
    }

    // Update herbivores (they eat plants; some may have been killed by predators this tick)
    for (const herb of herbivores) {
      if (herb.energy > 0) {
        updateHerbivore(herb, plants, newEntities, this.ids);
      }
    }

    // Update plants (skip reproduction if at cap)
    const atPlantCap = plants.length >= PLANT_CAP;
    for (const plant of plants) {
      if (plant.energy > 0) {
        if (atPlantCap) {
          // Still photosynthesize and drain, but skip reproduction
          plant.energy = Math.min(MAX_ENERGY, plant.energy + PLANT_ENERGY_REGEN);
          plant.energy -= PLANT_ENERGY_DRAIN;
        } else {
          updatePlant(plant, plants, newEntities, this.ids);
        }
      }
    }

    // Remove dead entities (energy <= 0)
    this.entities = this.entities.filter((e) => e.energy > 0);

    // Add newborns, respecting population caps
    const caps: Record<string, number> = {
      [Species.Plant]: PLANT_CAP,
      [Species.Herbivore]: HERBIVORE_CAP,
      [Species.Predator]: PREDATOR_CAP,
    };
    const counts = this.populationCounts;
    const current: Record<string, number> = {
      [Species.Plant]: counts.plants,
      [Species.Herbivore]: counts.herbivores,
      [Species.Predator]: counts.predators,
    };
    for (const e of newEntities) {
      if (current[e.species] < caps[e.species]) {
        this.entities.push(e);
        current[e.species]++;
      }
    }

    // Respawn extinct species to prevent permanent extinction
    this.respawnIfExtinct(Species.Plant, RESPAWN_COUNT * 3);
    this.respawnIfExtinct(Species.Herbivore, RESPAWN_COUNT);
    this.respawnIfExtinct(Species.Predator, RESPAWN_COUNT);
  }

  private respawnIfExtinct(species: Species, count: number): void {
    const alive = this.entities.some((e) => e.species === species);
    if (!alive) {
      for (let i = 0; i < count; i++) {
        this.entities.push(createEntity(species, this.ids));
      }
    }
  }

  getBySpecies(species: Species): Entity[] {
    return this.entities.filter((e) => e.species === species);
  }

  get populationCounts(): { plants: number; herbivores: number; predators: number } {
    let plants = 0;
    let herbivores = 0;
    let predators = 0;
    for (const e of this.entities) {
      if (e.species === Species.Plant) plants++;
      else if (e.species === Species.Herbivore) herbivores++;
      else predators++;
    }
    return { plants, herbivores, predators };
  }
}

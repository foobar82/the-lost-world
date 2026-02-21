import type { Entity } from "./types";
import { Species } from "./types";
import {
  INITIAL_PLANTS,
  INITIAL_HERBIVORES,
  INITIAL_PREDATORS,
} from "./constants";
import {
  createEntity,
  updatePlant,
  updateHerbivore,
  updatePredator,
  bounceIfAtEdge,
} from "./entities";

export class Simulation {
  entities: Entity[] = [];

  constructor() {
    this.seed();
  }

  private seed(): void {
    for (let i = 0; i < INITIAL_PLANTS; i++) {
      this.entities.push(createEntity(Species.Plant));
    }
    for (let i = 0; i < INITIAL_HERBIVORES; i++) {
      this.entities.push(createEntity(Species.Herbivore));
    }
    for (let i = 0; i < INITIAL_PREDATORS; i++) {
      this.entities.push(createEntity(Species.Predator));
    }
  }

  tick(): void {
    const newEntities: Entity[] = [];

    const plants = this.entities.filter((e) => e.species === Species.Plant);
    const herbivores = this.entities.filter((e) => e.species === Species.Herbivore);
    const predators = this.entities.filter((e) => e.species === Species.Predator);

    // Update predators first (they eat herbivores)
    for (const pred of predators) {
      updatePredator(pred, herbivores, newEntities);
      bounceIfAtEdge(pred);
    }

    // Update herbivores (they eat plants; some may have been killed by predators this tick)
    for (const herb of herbivores) {
      if (herb.energy > 0) {
        updateHerbivore(herb, plants, newEntities);
        bounceIfAtEdge(herb);
      }
    }

    // Update plants
    for (const plant of plants) {
      if (plant.energy > 0) {
        updatePlant(plant, plants, newEntities);
      }
    }

    // Remove dead entities (energy <= 0)
    this.entities = this.entities.filter((e) => e.energy > 0);

    // Add newborns
    this.entities.push(...newEntities);
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

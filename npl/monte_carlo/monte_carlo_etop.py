import logging
import numpy as np
import copy
from ase.units import kB
import warnings

from npl.monte_carlo.random_exchange_operator_etop import RandomExchangeOperatorExtended

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')


def setup_monte_carlo(start_particle, energy_calculator, feature_classifier):
    energy_key = energy_calculator.get_energy_key()

    feature_calculator = feature_classifier

    feature_calculator.compute_feature_vector(start_particle)
    energy_calculator.compute_energy(start_particle)

    exchange_operator = RandomExchangeOperatorExtended(0.5)
    exchange_operator.bind_particle(start_particle)

    return energy_key, feature_calculator, exchange_operator


def features_to_update(start_particle, exchanges):

    neighborhood = set()
    for exchange in exchanges:
        index1, index2 = exchange
        neighborhood.add(index1)
        neighborhood.add(index2)

        neighborhood = neighborhood.union(start_particle.neighbor_list[index1])
        neighborhood = neighborhood.union(start_particle.neighbor_list[index2])

    return neighborhood


def run_monte_carlo(temperature, max_steps, start_particle, energy_calculator, feature_classifier):

    energy_key, feature_calculator, exchange_operator = setup_monte_carlo(start_particle,
                                                                          energy_calculator,
                                                                          feature_classifier)
    logging.info("=====================================================")
    logging.info("Monte Carlo simulation")
    logging.info("=====================================================\n")
    logging.info("Starting Monte Carlo simulation")
    logging.info("Temperature: {}".format(temperature))
    logging.info("Max steps: {}".format(max_steps))
    logging.info("Starting energy: {:.3f}".format(start_particle.get_energy(
        energy_calculator.get_energy_key())))

    beta = 1 / (kB * temperature)

    start_energy = start_particle.get_energy(energy_key)
    lowest_energy = start_energy
    accepted_energies = [(lowest_energy, 0)]

    found_new_solution = False
    best_particle = copy.deepcopy(start_particle)

    total_steps = 0
    no_improvement = 0
    while no_improvement < max_steps:
        total_steps += 1
        if total_steps % 2000 == 0:
            logging.info("Step: {}".format(total_steps))
            logging.info("Lowest energy: {}".format(lowest_energy))

        exchanges = exchange_operator.random_exchange(start_particle)
        neighborhood = features_to_update(start_particle, exchanges)

        old_atom_features, change = feature_calculator.update_feature_vector(start_particle,
                                                                             neighborhood)

        energy_calculator.compute_energy(start_particle)
        new_energy = start_particle.get_energy(energy_key)

        delta_e = new_energy - start_energy

        acceptance_rate = min(1, np.exp(-beta * delta_e))
        if np.random.random() < acceptance_rate:
            if found_new_solution:
                if new_energy > start_energy:
                    start_particle.swap_symbols(exchanges)
                    best_particle = copy.deepcopy(start_particle)
                    # accepted_structures.append(copy.deepcopy(start_particle.get_ase_atoms()))
                    # best_particle['energies'][energy_key] = start_energy
                    start_particle.swap_symbols(exchanges)

            start_energy = new_energy
            accepted_energies.append((new_energy, total_steps))

            if new_energy < lowest_energy:
                no_improvement = 0
                lowest_energy = new_energy
                found_new_solution = True
            else:
                no_improvement += 1
                found_new_solution = False

        else:
            no_improvement += 1

            # roll back exchanges and make sure features and environments are up-to-date
            start_particle.swap_symbols(exchanges)
            start_particle.set_energy(energy_key, start_energy)
            feature_calculator.downgrade_feature_vector(start_particle, neighborhood,
                                                        old_atom_features, change)

            if found_new_solution:
                best_particle = copy.deepcopy(start_particle)
                # accepted_structures.append(copy.deepcopy(start_particle.get_ase_atoms()))
                # best_particle['energies'][energy_key] = copy.deepcopy(start_energy)
                found_new_solution = False

    accepted_energies.append((accepted_energies[-1][0], total_steps))

    return [best_particle, accepted_energies]

from ase.optimize import BFGS
from ase.calculators.emt import EMT

import numpy as np
import copy
import pickle
import sklearn.gaussian_process as gp
from sklearn.linear_model import BayesianRidge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


class EnergyCalculator:
    """Base class for an energy calculator.

    Valid implementations have to implement the compute_energy(particle) function.
    Energies are saved in the particle object with the key of the respective calculator.
    """
    def __init__(self):
        self.energy_key = None
        pass

    def compute_energy(self, particle):
        raise NotImplementedError

    def get_energy_key(self):
        return copy.deepcopy(self.energy_key)

    def set_energy_key(self, energy_key):
        self.energy_key = energy_key

    def save(self, name_file : str):
        with open(name_file, 'wb') as out:
            pickle.dump(self, out)

    @staticmethod
    def load(name_file):
        with open(name_file, 'rb') as calc:
            return pickle.load(calc)


class EMTCalculator(EnergyCalculator):
    """EMTCalculator is a class for calculating the energy of a nanoparticle using the Effective
    Medium Theory (EMT) method.

    Attributes:
        fmax (float): The maximum force tolerance for the BFGS optimizer. Default is 0.01.
        steps (int): The maximum number of steps for the BFGS optimizer. Default is 50.
        energy_key (str): The key used to store the calculated energy in the particle object.
        Default is 'EMT'.
        relax_atoms (bool): Flag indicating whether to relax the atoms during energy calculation.
        Default is False.

    Methods:
        compute_energy(particle):
            Compute the energy of the given nanoparticle using EMT.

        Initialize the EMTCalculator with the given parameters.

            fmax (float): The maximum force tolerance for the BFGS optimizer. Default is 0.01.
            steps (int): The maximum number of steps for the BFGS optimizer. Default is 50.
            relax_atoms (bool): Flag indicating whether to relax the atoms during energy
            calculation. Default is False.

        Compute the energy using EMT.

        BFGS is used for relaxation. By default, the atoms are NOT relaxed, i.e., the

            particle (Nanoparticle): The nanoparticle object for which the energy is to be
            calculated.

        Example:
            >>> from npl.calculators.energy_calculator import EMTCalculator
            >>> from npl.nanoparticle import Nanoparticle
            >>> particle = Nanoparticle()
            >>> particle.truncated_octahedron(7,2, {'Au' : 0.5, 'Ag' : 0.5})
            >>> calculator = EMTCalculator(fmax=0.02, steps=100, relax_atoms=True)
            >>> calculator.compute_energy(particle)
            >>> energy = particle.get_energy('EMT')
            >>> print(f"Computed energy: {energy}")
    """

    def __init__(self, fmax=0.01, steps=50, relax_atoms=False):
        EnergyCalculator.__init__(self)
        self.fmax = fmax
        self.steps = steps
        self.energy_key = 'EMT'
        self.relax_atoms = relax_atoms

    def compute_energy(self, particle):
        """Compute the energy using EMT.

        BFGS is used for relaxation. By default, the atoms are NOT relaxed, i.e. the
        geometry remains unchanged unless this is explicitly stated.

        Parameters:
            particle : Nanoparticle
            relax_atoms : bool
        """

        atoms = particle.get_ase_atoms(exclude_x=True)
        if not self.relax_atoms:
            atoms = atoms.copy()

        atoms.set_calculator(EMT())
        dyn = BFGS(atoms, logfile=None)
        dyn.run(fmax=self.fmax, steps=self.steps)

        energy = atoms.get_potential_energy()
        particle.set_energy(self.energy_key, energy)


class GPRCalculator(EnergyCalculator):
    """Energy calculator using global feature vectors and Gaussian Process Regression."""

    def __init__(self, feature_key, kernel=None, alpha=0.01, normalize_y=True):
        EnergyCalculator.__init__(self)
        if kernel is None:
            self.kernel = gp.kernels.ConstantKernel(1., (1e-1, 1e3)) * \
                          gp.kernels.RBF(1., (1e-3, 1e3))
        else:
            self.kernel = kernel

        self.alpha = alpha
        self.normalize_y = normalize_y
        self.GPR = None
        self.energy_key = 'GPR'
        self.feature_key = feature_key

    def fit(self, training_set, energy_key):
        """Fit the GPR model.

        The feature vectors with key = self.feature_key will be used for feature vectors. The
        energy with the specified energy_key will be the target function.

        Parameters:
            training_set : list of Nanoparticles
            energy_key : str
        """
        feature_vectors = [p.get_feature_vector(self.feature_key) for p in training_set]
        energies = [p.get_energy(energy_key) for p in training_set]

        self.GPR = gp.GaussianProcessRegressor(kernel=self.kernel,
                                               n_restarts_optimizer=20,
                                               alpha=self.alpha,
                                               normalize_y=self.normalize_y)
        self.GPR.fit(feature_vectors, energies)

    def compute_energy(self, particle):
        """Compute the energy using GPR.

        Assumes that a feature vector with key=self.feature_key is present in the particle.

        Parameters:
            particle : Nanoparticle
        """
        energy = self.GPR.predict([particle.get_feature_vector(self.feature_key)])[0]
        particle.set_energy(self.energy_key, energy)


class MixingEnergyCalculator(EnergyCalculator):
    """Compute the mixing energy using an arbitrary energy model.

    For the original energy model it is assumed that all previous steps in the energy pipeline, e.g.
    calculation of local environment, feature vectors etc. has been carried out.
    """
    def __init__(self, base_calculator=None, mixing_parameters=None, recompute_energies=False):
        EnergyCalculator.__init__(self)

        if mixing_parameters is None:
            self.mixing_parameters = dict()
        else:
            self.mixing_parameters = mixing_parameters

        self.base_calculator = base_calculator
        self.recompute_energies = recompute_energies
        self.energy_key = 'Mixing Energy'

    def compute_mixing_parameters(self, particle, symbols):
        """Compute the energies for the pure particles of the given symbols as reference points.

        Parameters:
            particle : Nanoparticle
            symbols : list of str
        """
        for symbol in symbols:
            particle.random_ordering({symbol: 1.0})
            self.base_calculator.compute_energy(particle)
            self.mixing_parameters[symbol] = particle.get_energy('EMT')

    def compute_energy(self, particle):
        """Compute the mixing energy of the particle using the base energy model.

        If energies have been computed using the same energy model as the base calculator they
        are reused if self.recompute_energies == False

        Parameters:
            particle : Nanoparticle
        """
        if self.recompute_energies:
            self.base_calculator.compute_energy(particle)

        energy_key = self.base_calculator.get_energy_key()
        mixing_energy = particle.get_energy(energy_key)

        n_atoms = particle.atoms.get_n_atoms()

        for symbol in particle.get_stoichiometry():
            mixing_energy -= self.mixing_parameters[symbol] * \
                                particle.get_stoichiometry()[symbol] / n_atoms

        particle.set_energy(self.energy_key, mixing_energy)


class BayesianRRCalculator(EnergyCalculator):
    """
    BayesianRRCalculator is a class for performing Bayesian Ridge Regression (BRR) on nanoparticle
    datasets.
    Attributes:
    -----------
    ridge : BayesianRidge
        The Bayesian Ridge Regression model.
        The key used to store energy values in the nanoparticles.
    feature_key : str
        The key used to extract feature vectors from the nanoparticles.
    Methods:
    --------
    __init__(self, feature_key):
        Initializes the BayesianRRCalculator with a given feature key.
    fit(self, training_set, energy_key, validation_set=None):
        Fits the Bayesian Ridge Regression model using the provided training set.
    validate(self, validation_set, energy_key):
        Validates the Bayesian Ridge Regression model using the provided validation set.
    get_coefficients(self):
        Returns the coefficients of the Bayesian Ridge Regression model.
    set_coefficients(self, new_coefficients):
        Sets the coefficients of the Bayesian Ridge Regression model.
    set_feature_key(self, feature_key):
        Sets the feature key used to extract feature vectors from the nanoparticles.
    compute_energy(self, particle):
        Computes the energy of a given nanoparticle using the Bayesian Ridge Regression model.
    Examples:
    ---------
    >>> from npl.calculators.energy_calculator import BayesianRRCalculator
    >>> calculator = BayesianRRCalculator(feature_key='some_feature_key')
    >>> training_set = [...]  # List of Nanoparticles for training
    >>> validation_set = [...]  # List of Nanoparticles for validation
    >>> calculator.fit(training_set, energy_key='some_energy_key', validation_set=validation_set)
    >>> coefficients = calculator.get_coefficients()
    >>> calculator.set_coefficients(new_coefficients)
    >>> calculator.set_feature_key('new_feature_key')
    >>> energy = calculator.compute_energy(some_nanoparticle)
    """

    def __init__(self, feature_key):
        EnergyCalculator.__init__(self)

        self.ridge = BayesianRidge(fit_intercept=False)
        self.energy_key = 'BRR'
        self.feature_key = feature_key

    def fit(self, training_set, energy_key, validation_set=None):
        """Fit the Bayesian Ridge Regression (BRR) model.

        Parameters:
        ----------
        training_set : list of Nanoparticles
            The dataset used for training the model.
        energy_key : str
            The key used to extract energy values from the nanoparticles.
        validation_set : float or list of Nanoparticles, optional
            If a float is provided, it represents the fraction of the training set to be used as
            the validation set.
            If a list is provided, it is used as the validation set directly. Default is None.
        Returns:
        -------
        None
        """
        if isinstance(validation_set, float):
            split_index = int(len(training_set) * validation_set)
            validation_set = training_set[split_index:]
            training_set = training_set[:split_index]

        feature_vectors = [p.get_feature_vector(self.feature_key) for p in training_set]
        energies = [p.get_energy(energy_key) for p in training_set]

        self.ridge.fit(feature_vectors, energies)

        if validation_set:
            self.validate(validation_set, energy_key)

    def validate(self, validation_set, energy_key):
        """Validate the Bayesian Ridge Regression (BRR) model.

        Parameters:
        ----------
        validation_set : list of Nanoparticles
            The dataset used for validating the model.
        energy_key : str
            The key used to extract energy values from the nanoparticles.

        Returns:
        -------
        None
        """
        pred_validation = [self.compute_energy(p) for p in validation_set]
        true_validation = [p.get_energy(energy_key) for p in validation_set]
        mae = mean_absolute_error(true_validation, pred_validation)
        rmse = root_mean_squared_error(true_validation, pred_validation)
        print('Mean Absolute error {:.4f} meV/atom'.format(mae))
        print('Root Mean Square error {:.4f} meV/atom'.format(rmse))

    def get_coefficients(self):
        return self.ridge.coef_

    def set_coefficients(self, new_coefficients):
        self.ridge.coef_ = new_coefficients

    def set_feature_key(self, feature_key):
        self.feature_key = feature_key

    def compute_energy(self, particle):
        """Compute the energy using BRR.

        Assumes that a feature vector with key=self.feature_key is present in the particle.

        Parameters:
            particle : Nanoparticle
        """
        feature_vector = particle.get_feature_vector(self.feature_key)
        # brr_energy = self.ridge.predict([particle.get_feature_vector(self.feature_key)])
        # brr_energy = np.dot(np.transpose(self.ridge.coef_),
        # particle.get_feature_vector(self.feature_key))
        brr_energy = np.dot(np.transpose(self.ridge.coef_), feature_vector)
        particle.set_energy(self.energy_key, brr_energy)
        return brr_energy


class DipoleMomentCalculator:

    def __init__(self):
        self.total_dipole_moment = None
        self.dipole_moments = None
        self.environments = None

    def compute_dipole_moment(self, particle, charges=[1, -1]):

        symbols = particle.get_all_symbols()
        fake_charges = {symbols[0] : charges[0], symbols[1] : charges[1]}
        partial_charges = [fake_charges[symbol] for symbol in particle.get_symbols()]

        dipole_moments = []
        environments = []
        for central_atom_idx in particle.get_atom_indices_from_coordination_number([12]):
            particle.translate_atoms_positions(particle.get_position(central_atom_idx))
            dipole_moment = 0
            for atom_idx in particle.get_coordination_atoms(central_atom_idx):
                dipole_moment += partial_charges[atom_idx] * particle.get_position(atom_idx)

            dipole_moments.append(np.linalg.norm(dipole_moment))
            environments.append(particle.get_coordination_atoms(central_atom_idx))

        self.total_dipole_moment = np.average(dipole_moments)/particle.get_n_atoms()
        self.dipole_moments = dipole_moments
        self.environments = environments

    def get_total_dipole_moment(self):
        return self.total_dipole_moment

    def get_dipole_moments(self):
        return self.dipole_moments

    def get_environments(self):
        return self.environments


class LateralInteractionCalculator:

    def __init__(self):
        EnergyCalculator.__init__(self)
        self.interaction_matrix = None
        self.energy_key = 'Lateral Interaction'
        self.a = 6

    def construct_interatomic_potential_matrix(self, particle):
        def construct_adsorbate_grid(particle):
            from npl.core.adsorption import PlaceAddAtoms
            particle.construct_adsorption_list()
            n_sites = particle.get_total_number_of_sites()
            ads_site_list = particle.get_adsorption_list()
            ads_placer = PlaceAddAtoms(particle.get_all_symbols())
            ads_placer.bind_particle(particle)
            adsorbate_positions = [list(ads_site_list[site]) for site in range(n_sites)]
            particle = ads_placer.place_add_atom(particle, 'O', adsorbate_positions)
            return particle

        def get_adsorbate_distance_matrix(particle, n_atoms_np):
            ase_atoms = particle.get_ase_atoms()
            adsorbate_all_distances = ase_atoms.get_all_distances()[n_atoms_np:]
            distance_matrix = np.array([row[n_atoms_np:] for row in adsorbate_all_distances])
            return distance_matrix

        n_atoms_np = particle.get_n_atoms()
        particle = construct_adsorbate_grid(particle)
        distance_matrix = get_adsorbate_distance_matrix(particle, n_atoms_np)
        interaction_matrix = np.zeros(distance_matrix.shape)
        interaction_matrix = self.a / distance_matrix**2

        dimension = len(interaction_matrix)
        for i in np.arange(dimension):
            interaction_matrix[i][i] = 0

        self.interaction_matrix = interaction_matrix

    def bind_grid(self, particle):
        particle_for_grid = copy.deepcopy(particle)
        self.construct_interatomic_potential_matrix(particle_for_grid)

    def compute_energy(self, particle):
        lateral_interaction = 0
        occupied_sites_indices = particle.get_occupation_status_by_indices(1)
        for idx, site_index in enumerate(occupied_sites_indices):
            for pair_index in occupied_sites_indices[idx:]:
                lateral_interaction += self.interaction_matrix[site_index][pair_index]
        particle.set_energy(self.energy_key, lateral_interaction)

# TODO move to relevant file -> Basin Hopping, Local optimization
# TODO remove scaling factors from topological descriptors


def compute_coefficients_for_linear_topological_model(global_topological_coefficients, symbols,
                                                      n_atoms):
    coordination_numbers = list(range(13))
    symbols_copy = copy.deepcopy(symbols)
    symbols_copy.sort()
    symbol_a = symbols_copy[0]
    print("Coef symbol_a: {}".format(symbol_a))

    e_aa_bond = global_topological_coefficients[0]/n_atoms
    e_bb_bond = global_topological_coefficients[1]/n_atoms
    e_ab_bond = global_topological_coefficients[2]/n_atoms

    coefficients = []
    total_energies = []
    for symbol in symbols_copy:
        for cn_number in coordination_numbers:
            for n_symbol_a_atoms in range(cn_number + 1):
                energy = 0

                if symbol == symbol_a:
                    energy += (global_topological_coefficients[3]*0.1)  # careful...
                    energy += (n_symbol_a_atoms*e_aa_bond/2)
                    energy += ((cn_number - n_symbol_a_atoms)*e_ab_bond/2)
                    energy += (global_topological_coefficients[4 + cn_number])

                    total_energy = energy
                    total_energy += n_symbol_a_atoms*e_aa_bond/2
                    total_energy += (cn_number - n_symbol_a_atoms)*e_ab_bond/2
                else:
                    energy += (n_symbol_a_atoms*e_ab_bond/2)
                    energy += ((cn_number - n_symbol_a_atoms)*e_bb_bond/2)

                    total_energy = energy
                    total_energy += n_symbol_a_atoms*e_ab_bond/2
                    total_energy += (cn_number - n_symbol_a_atoms)*e_bb_bond/2

                coefficients.append(energy)
                total_energies.append(total_energy)

    coefficients = np.array(coefficients)

    return coefficients, total_energies


def compute_coefficients_for_shape_optimization(global_topological_coefficients, symbols):
    coordination_numbers = list(range(13))
    symbols_copy = copy.deepcopy(symbols)
    symbols_copy.sort()

    e_aa_bond = global_topological_coefficients[0]

    coordination_energies_a = dict()
    for index, cn in enumerate(coordination_numbers):
        coordination_energies_a[cn] = global_topological_coefficients[index + 1]

    coefficients = []
    total_energies = []
    for cn_number in coordination_numbers:
        for n_symbol_a_atoms in range(cn_number + 1):
            energy = 0

            energy += (n_symbol_a_atoms*e_aa_bond/2)
            energy += (coordination_energies_a[cn_number])

            total_energy = energy + n_symbol_a_atoms*e_aa_bond/2

            coefficients.append(energy)
            total_energies.append(total_energy)

    coefficients += [0]*len(coefficients)
    total_energies += [0]*len(total_energies)

    coefficients = np.array(coefficients)

    return coefficients, total_energies

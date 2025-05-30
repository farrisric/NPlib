from ase import Atoms
from ase.io import read, write
import pickle
from npl.core.atom_wrapper import AtomWrapper
from npl.core.neighbor_list import NeighborList
from npl.core.adsorption import AdsorptionSiteList
from npl.utils import get_crystalline_structure


# TODO update local environment handling with keys
class BaseNanoparticle:
    """
    Represent a nanoparticle.
    a NeighborList object. Multiple energies, feature vectors, and local environments
    can be accessed by storing them with their respective key.
    BaseNanoparticle is a data holder class in the sense that all common calculations
    such as the calculation of feature vectors, atomic descriptors, or energies should
    This ensures that BaseNanoparticle remains as general as possible.
    For project-specific behavior, the Nanoparticle class, which inherits from
    BaseNanoparticle, should be used.
    Attributes:
        atoms (AtomWrapper): An object that wraps atomic information.
        neighbor_list (NeighborList): An object that stores the neighbor list.
        adsorption_site_list (AdsorptionSiteList): An object that stores adsorption sites.
        energies (dict): A dictionary to store multiple energy values.
        local_environments (dict): A dictionary to store local environments.
        atom_features (dict): A dictionary to store atomic features.
        feature_vectors (dict): A dictionary to store feature vectors.
        """
    def __init__(self):
        self.atoms = AtomWrapper()
        self.neighbor_list = NeighborList()
        self.adsorption_site_list = AdsorptionSiteList()

        self.energies = dict()

        self.local_environments = dict()
        self.atom_features = dict()
        self.feature_vectors = dict()

    def get_geometrical_data(self):
        """Return the geometrical information of the nanoparticle as dictionary.

        This function returns a dict containing positions and the neighbor list, but not the
        symbols. In that way, nanoparticles with different orderings can share the same
        geometry.
        """
        data = dict()
        data['neighbor_list'] = self.neighbor_list.list
        data['positions'] = self.atoms.get_positions()

        return data

    def get_as_dictionary(self, fields=None):
        """Return the nanoparticle in the form of a JSON-compatible dictionary.

        Parameters:

            fields: list of str
                Specifies which piece of information the user wants to save. Accepted values are:
                'energies', 'symbols', 'positions', 'atom_features', 'local_environments',
                'neighbor_list', 'feature_vectors'.

        """

        full_particle_dict = {'energies': self.energies,
                              'symbols': list(self.atoms.get_symbols()),
                              'positions': self.atoms.get_positions(),
                              'atom_features': self.atom_features,
                              'local environments': self.local_environments,
                              'neighbor_list': dict(self.neighbor_list.list),
                              'feature_vectors': self.feature_vectors}

        if fields is None:
            return full_particle_dict
        else:
            data = {}
            for field in fields:
                data[field] = full_particle_dict[field]
            return data

    def save_npl_format(self, filename, fields, filename_geometry=None):
        """Save the nanoparticle by first exporting it to a dictionary and then using pickle.

        The nanoparticle can be stored into two separate files, one of which holds the geometry
        (i.e. positions and neighbor list, not the symbols!). This allows to reuse the same
        geometry for several particles with different ordering.

        Parameters:

            filename: str
            filename.

            fields: list of str
            Specify the piece of information to save. See get_as_dictionary() for explanation.

            filename_geometry: str
            Filename of file in which the geometrical information will be stored. This is
            independent of the fields variable.
        """
        data = self.get_as_dictionary(fields)
        pickle.dump(data, open(filename, 'wb'))

        if filename_geometry is not None:
            geometrical_data = self.get_geometrical_data()
            pickle.dump(geometrical_data, open(filename_geometry, 'wb'))

    def build_from_dictionary(self, particle_dict, geometrical_dict=None):
        """Construct a nanoparticle based on a representation as dictionary.

        Takes either one dictionary for the whole nanoparticle or two if one only specifies
        the geometry.

        Parameter:

            particle_dict: dict
            Dictionary containing all the necessary information to build a nanoparticle. See
            get_as_dictionary() for valid keys.

            geometrical_dict: dict
            Dictionary containing positions and neighbor list. If particle_dict also contains
            geometrical information, geometrical_dict will still be used.
        """
        if geometrical_dict is None:
            positions = particle_dict['positions']
            symbols = particle_dict['symbols']
        else:
            positions = geometrical_dict['positions']
            if particle_dict is None:
                symbols = ['X'] * len(positions)
            else:
                symbols = particle_dict['symbols']

        atoms = Atoms(symbols, positions)
        self.atoms.add_atoms(atoms)

        if particle_dict is None:
            self.neighbor_list.list = geometrical_dict['neighbor_list']
        else:
            if 'neighbor_list' in particle_dict:
                self.neighbor_list.list = particle_dict['neighbor_list']

        if particle_dict is not None:
            if 'neighbor_list' in particle_dict:
                self.neighbor_list.list = particle_dict['neighbor_list']
        if geometrical_dict is not None:
            if 'neighbor_list' in geometrical_dict:
                self.neighbor_list.list = geometrical_dict['neighbor_list']

        if particle_dict is not None:
            self.energies = particle_dict['energies']

            if 'feature_vectors' in particle_dict:
                self.feature_vectors = particle_dict['feature_vectors']
            if 'atom_features' in particle_dict:
                self.atom_features = particle_dict['atom_features']

            if 'local_environments' in particle_dict:
                self.local_environments = particle_dict['local_environments']

    def load_npl_format(self, filename, filename_geometry=None):
        """Load a nanoparticle file in the NPL format.

        Files are loaded using pickle.

        Parameter:

            filename: str
            Filename of the particle.

            filename_geometry: str
            Filename of geometrical data.
        """
        if filename is not None:
            dictionary = pickle.load(open(filename, 'rb'))
        else:
            dictionary = None

        if filename_geometry is not None:
            topological_data = pickle.load(open(filename_geometry, 'rb'))
            self.build_from_dictionary(dictionary, topological_data)
        else:
            self.build_from_dictionary(dictionary)

    def read(self, filename, construct_neighbor_list=True, energy_key=None,
             crystal_structure=False):
        """Wrapper class around ase.io.read.

        By default a neighbor list will be constructed. Energies that are present in
        the atoms object, e.g. from after a DFT calculation can be given an individual
        energy key.

        Parameters:
            filename: str
            construct_neighbor_list: bool
            energy_key : str
        """
        atoms = read(filename)
        if crystal_structure:
            atoms = get_crystalline_structure(atoms)
        self.atoms.add_atoms(atoms)

        if construct_neighbor_list:
            self.construct_neighbor_list()

        if energy_key is not None:
            self.set_energy(energy_key, atoms.get_potential_energy())

    def write(self, filename):
        """Wrapper around the ase.io.write method.

        NPL specific information will NOT be stored, including energies

        Parameters:
            filename: str
        """
        atoms = self.atoms.get_ase_atoms()
        write(filename, atoms)

    def add_atoms(self, atoms, recompute_neighbor_list=True, crystal=False):
        """Add atoms to the nanoparticle.

        Neighbor list will be recomputed after the addition by default.

        Parameters:

            atoms: Atoms
            recompute_neighbor_list: bool
        """
        if crystal:
            atoms = get_crystalline_structure(atoms)
        self.atoms.add_atoms(atoms)

        if recompute_neighbor_list:
            self.construct_neighbor_list()

    def remove_atoms(self, atom_indices, recompute_neighbor_list=True):
        """Remove atoms from the nanoparticle.

        Neighbor list will be recomputed after the removal by default.

        Parameters:

            atom_indices: list/array of int
            Indices of the atoms to be removed.

            recompute_neighbor_list: bool
        """
        self.atoms.remove_atoms(atom_indices)

        if recompute_neighbor_list:
            self.construct_neighbor_list()

    def swap_symbols(self, index_pairs):
        """Swap the elements of the specified pairs.

        Parameters:

            index_pairs: list of tuple
            List that contains tuples which contain two indices, respectively, of atoms where the
            symbols will be exchanged.
        """
        self.atoms.swap_symbols(index_pairs)

    def transform_atoms(self, atom_indices, new_symbols):
        """Change the symbol for the given atoms.

        The first atom will be changed to the first new symbol, the second atom to the second
        new symbol etc.

        Parameters:

            atom_indices: list/array of int

            new_symbols: list of str
        """
        self.atoms.transform_atoms(atom_indices, new_symbols)

    def random_ordering(self, stoichiometry):
        """Create a random chemical ordering for the particle with the given stoichiometry.

        Parameters:
            stoichiometry: dict
            Dictionary containing key-value pairs of the form symbol - number of atoms. Fractions
            are also supported, but care for round-off errors.

        Example:
              random_ordering({'Pt' : 79} \n
              random_ordering({'Pt' : 0.5, 'Au' : 0.5})
        """
        # account for stoichiometries given as proportions instead of absolute numbers
        if sum(stoichiometry.values()) == 1:
            n_atoms = self.atoms.get_n_atoms()
            transformed_stoichiometry = dict()
            for symbol in sorted(stoichiometry):
                transformed_stoichiometry[symbol] = int(n_atoms * stoichiometry[symbol])

            # adjust for round-off error
            if sum(transformed_stoichiometry.values()) != n_atoms:
                diff = n_atoms - sum(transformed_stoichiometry.values())
                transformed_stoichiometry[sorted(stoichiometry)[0]] += diff

            # print('Resulting stoichiometry: {}'.format(transformed_stoichiometry))
            self.atoms.random_ordering(transformed_stoichiometry)
        else:
            self.atoms.random_ordering(stoichiometry)

    def translate_atoms_positions(self, position):
        """ Shifts the origin of the coordinates towards a given position.

        Useful to center the origin on an atom, when the position passed
        are the coordinates of the atom.

        Parameters:
            position: array
            Array that contains x y z coordinates. """
        self.atoms.translate_atoms_positions(position)

    def get_indices(self):
        """Convenience function for range(n_atoms)."""
        return self.atoms.get_indices()

    def get_n_bonds(self):
        """Return the number of bonds, requires valid neighbor list."""
        return self.neighbor_list.get_n_bonds()

    def get_all_symbols(self):
        """Return list of symbols that occur at least once in the particle"""
        return self.atoms.get_all_symbols()

    def get_symbol(self, index):
        """Return symbol of the given index."""
        return self.atoms.get_symbol(index)

    def get_symbols(self, indices=None):
        """Return the elements in order of the passed indices.

        By default symbols for all atoms are returned.

        Parameters:
            indices : list/array of int
        """
        return self.atoms.get_symbols(indices)

    def get_indices_by_symbol(self, symbol):
        """Return indices of all atoms of the respective symbol.

        Parameters:
            symbol: str
        """
        return self.atoms.get_indices_by_symbol(symbol)

    def construct_neighbor_list(self, exclude_x=True, scale_factor=1.0):
        """Construct neighbor list.

        Vacancies denoted by symbol 'X' are excluded by the default.
        """
        stripped_atoms = self.get_ase_atoms(exclude_x=exclude_x)
        self.neighbor_list.construct(stripped_atoms, scale_factor=scale_factor)

    def get_atom_indices_from_coordination_number(self, coordination_numbers, symbol=None):
        """Return atom indices of atoms with certain coordination numbers.

        In addition, the search can be restricted to a spcific symbol.

        Parameters:
            coordination_numbers : list/array of int
            symbol : str
        """
        if symbol is None:
            return list(
                filter(lambda x: self.get_coordination_number(x) in coordination_numbers,
                       self.atoms.get_indices()))
        else:
            return list(filter(lambda x: self.get_coordination_number(x) in coordination_numbers
                        and self.atoms.get_symbol(x) == symbol, self.atoms.get_indices()))

    def get_coordination_number(self, atom_idx):
        """
        Get the coordination number for a given atom.

        The coordination number is the number of nearest neighbors
        surrounding a specific atom in the nanoparticle.

        Parameters:
        atom_idx (int): The index of the atom for which to get the coordination number.

        Returns:
        int: The coordination number of the specified atom.
        """
        return self.neighbor_list.get_coordination_number(atom_idx)

    def get_coordination_atoms(self, atom_idx):
        """
        Get the coordination atoms for a given atom index.

        Parameters:
        atom_idx (int): The index of the atom for which to find the coordination atoms.

        Returns:
        list: A list of coordination atoms for the specified atom index.
        """
        return self.neighbor_list.get_coordination_atoms(atom_idx)

    def get_generalized_coordination_number(self, indices):
        """
        Calculate the generalized coordination number for the given indices.

        Parameters:
        indices (list or array-like): The indices of the atoms for which the
                                      generalized coordination number is to be calculated.

        Returns:
        float: The generalized coordination number for the specified indices.
        """
        return self.neighbor_list.get_generalized_coordination_number(indices)

    def get_generalized_coordination_numbers(self, sites):
        """
        Calculate the generalized coordination numbers for a list of sites.

        This method iterates over a list of sites, calculates the generalized
        coordination number for each site using the `get_generalized_coordination_number`
        method, and groups the sites by their generalized coordination numbers in a dictionary.

        Args:
            sites (list): A list of sites for which to calculate the generalized coordination
            numbers.

        Returns:
            dict: A dictionary where the keys are generalized coordination numbers and the values
                  are lists of sites that have the corresponding generalized coordination number.
        """

        gcn_dict = dict()
        for site in sites:
            gen_cn = self.get_generalized_coordination_number(site)
            try:
                gcn_dict[gen_cn].append(site)
            except KeyError:
                gcn_dict[gen_cn] = [site]
        return gcn_dict

    def get_atoms_in_the_surface_plane(self, atom_idx, edges_corner=False):
        """
        Get the atoms in the surface plane of a nanoparticle.

        Parameters:
        -----------
        atom_idx : int
            The index of the atom for which to find the surface plane atoms.
        edges_corner : bool, optional
            If True, include atoms at the edges and corners of the surface plane.
            Default is False.

        Returns:
        --------
        list
            A list of atom indices that are in the surface plane.
        """
        return self.neighbor_list.get_atoms_in_the_surface_plane(atom_idx,
                                                                 edges_corner=edges_corner)

    def get_n_atoms(self):
        """Return the number of atoms."""
        return self.atoms.get_n_atoms()

    def get_neighbor_list(self):
        """
        Retrieve the list of neighboring particles.

        Returns:
            list: A list containing the neighboring particles.
        """
        return self.neighbor_list

    def get_ase_atoms(self, indices=None, exclude_x=True):
        """Return an ase Atoms object representing the nanoparticle.

        By default all atoms will be returned except vacancies.

        Parameters:
            indices: list/array of int
            Only the selected atoms will be returned. If None is given, all indices will be
            returned by default.

            exclude_x: bool
            Exclude vacancies denoted by symbol 'X' from the atoms object. Necessary
            e.g. for energy calculations
        """
        if exclude_x and 'X' in self.get_stoichiometry():
            vacancies = self.get_indices_by_symbol('X')
            if indices is None:
                valid_indices = set(self.get_indices()).difference(vacancies)
            else:
                valid_indices = set(indices).difference(vacancies)

            return self.atoms.get_ase_atoms(list(valid_indices))
        else:
            return self.atoms.get_ase_atoms(indices)

    def get_atoms(self, indices):
        """
        Retrieve atoms based on the provided indices.

        Parameters:
        indices (list or array-like): A list or array of indices specifying which atoms to retrieve.

        Returns:
        list: A list of atoms corresponding to the specified indices.
        """
        return self.atoms.get_atoms(indices)

    def get_position(self, idx):
        return self.atoms.get_position(idx)

    def get_stoichiometry(self):
        return self.atoms.get_stoichiometry()

    def get_n_atoms_of_symbol(self, symbol):
        return self.atoms.get_n_atoms_of_symbol(symbol)

    def set_energy(self, energy_key, energy):
        self.energies[energy_key] = energy

    def get_energy(self, energy_key):
        return self.energies[energy_key]

    def has_energy(self, energy_key):
        if energy_key in self.energies:
            return True
        return False

    def set_feature_vector(self, feature_key, feature_vector):
        self.feature_vectors[feature_key] = feature_vector

    def get_feature_vector(self, feature_key):
        """
        Retrieve the feature vector associated with the given feature key.

        Args:
            feature_key (str): The key corresponding to the desired feature vector.

        Returns:
            numpy.ndarray: The feature vector associated with the provided feature key.

        Raises:
            KeyError: If the feature_key is not found in the feature_vectors dictionary.
        """
        return self.feature_vectors[feature_key]

    def set_atom_features(self, atom_features, feature_key):
        """
        Sets the features of an atom in the nanoparticle.

        Parameters:
        atom_features (dict): A dictionary containing the features of the atom.
        feature_key (str): The key under which the atom features will be stored in the
        atom_features dictionary.

        Returns:
        None
        """
        self.atom_features[feature_key] = atom_features

    def set_atom_feature(self, feature_key, index, atom_feature):
        """
        Sets the feature of a specific atom in the nanoparticle.

        Parameters:
        feature_key (str): The key identifying the feature to be set.
        index (int): The index of the atom whose feature is to be set.
        atom_feature: The new feature value to be assigned to the atom.

        Returns:
        None
        """
        self.atom_features[feature_key][index] = atom_feature

    def get_atom_feature(self, feature_key, index):
        """
        Retrieve a specific feature of an atom by its index.

        Args:
            feature_key (str): The key corresponding to the desired feature.
            index (int): The index of the atom for which the feature is to be retrieved.

        Returns:
            The value of the specified feature for the atom at the given index.
        """
        return self.atom_features[feature_key][index]

    def get_atom_features(self, feature_key):
        """
        Retrieve or initialize the features of an atom based on the given feature key.

        If the feature key does not exist in the atom_features dictionary, it initializes
        an empty dictionary for that feature key.

        Args:
            feature_key (str): The key representing the specific feature of the atom.

        Returns:
            dict: The dictionary containing the features associated with the given feature key.
        """
        if feature_key not in self.atom_features:
            self.atom_features[feature_key] = dict()
        return self.atom_features[feature_key]

    def set_local_environment(self, atom_idx, local_environment):
        """
        Sets the local environment for a specified atom.

        Parameters:
        atom_idx (int): The index of the atom for which the local environment is being set.
        local_environment (object): The local environment to be assigned to the atom.
        """
        self.local_environments[atom_idx] = local_environment

    def get_local_environment(self, atom_idx):
        """
        Retrieve the local environment of a specified atom.

        Parameters:
        atom_idx (int): The index of the atom for which the local environment is to be retrieved.

        Returns:
        object: The local environment corresponding to the specified atom index.
        """
        return self.local_environments[atom_idx]

    def set_local_environments(self, local_environments):
        """
        Sets the local environments for the nanoparticle.

        Parameters:
        local_environments (dict): A dictionary containing the local environments to be set.
        """
        self.local_environments = local_environments

    def get_local_environments(self):
        """
        Retrieve the local environments of the nanoparticle.

        Returns:
            list: A list containing the local environments.
        """
        return self.local_environments

    def is_pure(self):
        """
        Check if the nanoparticle is composed of a single element.

        Returns:
            bool: True if the nanoparticle is composed of a single element, False otherwise.
        """
        if len(self.get_all_symbols()) == 1:
            return True
        return False

    # ADSORPTION SECTION

    def construct_adsorption_list(self):
        self.adsorption_site_list.construct(self)

    def get_adsorption_list(self):
        return self.adsorption_site_list

    def get_adsorption_as_list(self):
        n_sites = self.get_total_number_of_sites()
        adsorption_site_list = [list(self.adsorption_site_list[x]) for x in range(n_sites)]
        return adsorption_site_list

    def get_total_number_of_sites(self):
        return self.adsorption_site_list.get_total_number_of_sites()

    def get_site_atom_indices(self, index):
        return self.adsorption_site_list.get_site_atom_indices(index)

    def random_occupation(self, number_of_adsorbates):
        self.adsorption_site_list.random_occupation(number_of_adsorbates)

    def get_occupation_vector(self):
        """
        Retrieve the occupation vector from the adsorption site list.

        Returns:
            list: A list representing the occupation vector of the adsorption sites.
        """
        return self.adsorption_site_list.get_occupation_vector()

    def get_occupation_status_by_indices(self, status):
        """
        Retrieve the occupation status of adsorption sites by their indices.

        Args:
            status (list or array-like): A list or array of indices representing the adsorption
            sites.

        Returns:
            list: A list of occupation statuses corresponding to the provided indices.
        """
        return self.adsorption_site_list.get_occupation_status_by_indices(status)

    def get_number_of_adsorbates(self):
        """
        Get the number of adsorbates on the nanoparticle.

        This method retrieves the number of adsorbates from the adsorption site list.

        Returns:
            int: The number of adsorbates.
        """
        return self.adsorption_site_list.get_number_of_adsorbates()

    def get_indices_of_adsorbates(self):
        """
        Retrieve the indices of adsorbates.

        This method returns the indices of adsorption sites that are occupied by adsorbates.

        Returns:
            list: A list of indices where adsorbates are present.
        """
        return self.adsorption_site_list.get_occupation_status_by_indices(1)

    def swap_status(self, index_pairs):
        """
        Swap the status of adsorption sites based on the provided index pairs.

        Parameters:
        index_pairs (list of tuple): A list of tuples where each tuple contains two indices.
                                     The status of the adsorption sites at these indices will be
                                     swapped.
        """
        self.adsorption_site_list.swap_status(index_pairs)

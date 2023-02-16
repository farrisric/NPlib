from abc import ABC, abstractmethod

class BaseOperator(ABC):
    """An abstract base class for operation that can be performed 
    in a global optimization run.
    
    Parameters
    ----------
    name:
        identifier of the descriptor
    """

    def __init__(self):
        self.operations = []
        pass

    @abstractmethod
    def perform_operation(self):
        pass

    @abstractmethod
    def revert_operation(self):
        pass

    def execute_swap_operation(self, a, exchange, swap):
        ex1, ex2 = exchange
        swap1, swap2 = swap
        a[ex1][swap1], a[ex2][swap2] = a[ex2][swap2], a[ex1][swap1]